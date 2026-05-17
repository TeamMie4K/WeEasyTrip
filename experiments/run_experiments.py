# -*- coding: utf-8 -*-
"""
run_experiments.py — WeEasyTrip (Thesis)
Runs 30 trials × 3 algorithms × 3 scenarios
Outputs: results/results.json, results/stats.txt, results/convergence.png
"""
import sys, os, time, json, random, copy, statistics, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'algorithm'))

from utils import load_data, evaluate_route, DAY_TIME_BUDGET
from greedy import greedy_solve
from genetic import genetic_solve
from hybrid import hybrid_solve

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'phuket_pois.json')
OUT_DIR   = os.path.join(os.path.dirname(__file__), 'results')
os.makedirs(OUT_DIR, exist_ok=True)

TRIALS = 30

# ─── Scenarios ──────────────────────────────────────────────────────────────
# S1: งบน้อย 3 วัน  — Hotel idx 2 (Anchalee Inn, 400/คืน × 2 = 800)
# S2: งบกลาง 5 วัน  — Hotel idx 7 (Ibis Phuket Patong, 1100/คืน × 4 = 4400)
# S3: งบสูง  7 วัน  — Hotel idx 12 (Novotel Surin, 2400/คืน × 6 = 14400)
SCENARIOS = [
    {
        'label':        'S1_Short_Budget',
        'total_budget': 10_000,
        'days':         3,
        'hotel_idx':    2,
        'scoring_mode': 'ratio',
    },
    {
        'label':        'S2_Medium_Standard',
        'total_budget': 15_000,
        'days':         5,
        'hotel_idx':    7,
        'scoring_mode': 'ratio',
    },
    {
        'label':        'S3_Long_Premium',
        'total_budget': 25_000,
        'days':         7,
        'hotel_idx':    12,
        'scoring_mode': 'quality',
    },
]

GA_PARAMS     = dict(pop_size=50, generations=100, mutation_rate=0.3)
HYBRID_PARAMS = dict(pop_size=30, generations=60,  mutation_rate=0.3)


def activity_budget(sc, hotel):
    nights = max(1, sc['days'] - 1)
    return max(0.0, sc['total_budget'] - hotel['cost'] * nights)


def run_one(algo, pois, hotel, days, act_budget, scoring_mode, seed):
    random.seed(seed)
    t0 = time.perf_counter()

    if algo == 'Greedy':
        routes = greedy_solve(pois, hotel, days, act_budget, scoring_mode=scoring_mode)
        history = None
    elif algo == 'GA':
        routes, history = genetic_solve(pois, hotel, days, act_budget, **GA_PARAMS)
    else:  # Hybrid
        routes, history = hybrid_solve(pois, hotel, days, act_budget,
                                       scoring_mode=scoring_mode, **HYBRID_PARAMS)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    ev = evaluate_route(routes, hotel, act_budget)
    return {
        'score':   ev['total_score'],
        'cost':    ev['total_cost'],
        'valid':   ev['valid'],
        'time_ms': round(elapsed_ms, 1),
        'history': history,
    }


def stats_summary(values):
    if not values:
        return {'mean': 0, 'median': 0, 'stdev': 0, 'min': 0, 'max': 0}
    return {
        'mean':   round(statistics.mean(values), 3),
        'median': round(statistics.median(values), 3),
        'stdev':  round(statistics.stdev(values) if len(values) > 1 else 0.0, 3),
        'min':    round(min(values), 3),
        'max':    round(max(values), 3),
    }


def kruskal_wallis(groups):
    """Kruskal-Wallis H-test (non-parametric one-way ANOVA)"""
    all_vals = []
    group_labels = []
    for gi, g in enumerate(groups):
        all_vals.extend(g)
        group_labels.extend([gi] * len(g))
    n = len(all_vals)
    if n < 3:
        return 0.0, 1.0

    # Assign ranks (average rank for ties)
    sorted_idx = sorted(range(n), key=lambda i: all_vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and all_vals[sorted_idx[j]] == all_vals[sorted_idx[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[sorted_idx[k]] = avg_rank
        i = j

    # Compute H
    H = 0.0
    offset = 0
    for g in groups:
        if not g:
            continue
        group_ranks = ranks[offset:offset + len(g)]
        R = sum(group_ranks)
        H += (R ** 2) / len(g)
        offset += len(g)
    H = (12.0 / (n * (n + 1))) * H - 3 * (n + 1)

    # p-value approximation via chi-squared with df = k-1
    df = len([g for g in groups if g]) - 1
    p = 1.0
    if df > 0 and H > 0:
        # chi2 survival function approximation
        x = H / df
        p = math.exp(-H / 2) * sum(
            (H / 2) ** k / math.factorial(k)
            for k in range(df)
        ) if df <= 10 else max(0.0, 1.0 - (1 - math.exp(-H / 2)))
        p = max(0.0, min(1.0, p))
    return round(H, 4), round(p, 6)


def _avg_history(histories):
    if not histories:
        return []
    max_len = max(len(h) for h in histories)
    return [round(statistics.mean([h[i] for h in histories if i < len(h)]), 3)
            for i in range(max_len)]


def main():
    pois, hotels = load_data(DATA_PATH)
    print(f"Loaded {len(pois)} POIs, {len(hotels)} hotels\n")

    all_results = {}
    algos = ['Greedy', 'GA', 'Hybrid']

    for sc in SCENARIOS:
        hotel = hotels[sc['hotel_idx']]
        act_b = activity_budget(sc, hotel)
        nights = sc['days'] - 1
        print(f"{'=' * 60}")
        print(f"Scenario : {sc['label']}")
        print(f"Hotel    : {hotel['id']} {hotel['name_en']} ({hotel['cost']}/night × {nights} = {hotel['cost'] * nights})")
        print(f"Act.Bdgt : {act_b:.0f}  (total={sc['total_budget']})")
        print(f"Days     : {sc['days']}")
        sc_res = {}

        for algo in algos:
            n_trials = 1 if algo == 'Greedy' else TRIALS
            print(f"  [{algo:6s}] ", end='', flush=True)
            trials, histories = [], []

            for t in range(n_trials):
                r = run_one(algo, list(pois), hotel, sc['days'],
                            act_b, sc['scoring_mode'], seed=t)
                trials.append(r)
                if r['history']:
                    histories.append(r['history'])
                print('.', end='', flush=True)

            scores = [r['score'] for r in trials]
            valid  = [r for r in trials if r['valid']]
            times  = [r['time_ms'] for r in trials]
            print(f"  score={statistics.mean(scores):.1f}"
                  f"±{statistics.stdev(scores) if len(scores) > 1 else 0:.1f}"
                  f"  valid={len(valid)}/{n_trials}"
                  f"  time={statistics.mean(times):.0f}ms")

            sc_res[algo] = {
                'n_trials':    n_trials,
                'valid_count': len(valid),
                'score_stats': stats_summary(scores),
                'time_stats':  stats_summary(times),
                'avg_history': _avg_history(histories),
                'trials': [{k: v for k, v in r.items() if k != 'history'} for r in trials],
            }

        # Kruskal-Wallis test across 3 algorithms
        groups = [[r['score'] for r in sc_res[a]['trials']] for a in algos]
        H, p = kruskal_wallis(groups)
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
        print(f"  KW: H={H:.3f} p={p:.4f} {sig}\n")
        sc_res['kruskal'] = {'H': H, 'p': p, 'sig': sig}
        all_results[sc['label']] = sc_res

    # Save JSON
    with open(os.path.join(OUT_DIR, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    write_stats_report(all_results, algos, OUT_DIR)

    try:
        plot_convergence(all_results, algos, OUT_DIR)
        print("Saved: results/convergence.png")
    except Exception as e:
        print(f"Plot skipped: {e}")

    print_summary(all_results, algos)


def write_stats_report(all_results, algos, out_dir):
    lines = [
        "=" * 70,
        "EXPERIMENT RESULTS — WeEasyTrip (Phuket B-TOPTW)",
        f"Stochastic trials: {TRIALS}  |  Greedy: 1 (deterministic)",
        f"GA params: pop=50, gen=100, mut=0.3",
        f"Hybrid params: pop=30, gen=60, mut=0.3 + early-stop(15) + 2-opt",
        "=" * 70,
    ]
    for sc_label, sc_data in all_results.items():
        lines.append(f"\n[ {sc_label} ]")
        lines.append(f"{'Algorithm':<10} {'Mean':>8} {'Std':>8} {'Max':>8} "
                     f"{'Min':>8} {'Time(ms)':>10} {'Valid':>6}")
        lines.append("-" * 62)
        for algo in algos:
            d  = sc_data[algo]
            ss = d['score_stats']
            ts = d['time_stats']
            lines.append(
                f"{algo:<10} {ss['mean']:>8.2f} {ss['stdev']:>8.2f} "
                f"{ss['max']:>8.2f} {ss['min']:>8.2f} "
                f"{ts['mean']:>10.1f} {d['valid_count']:>3}/{d['n_trials']:<3}"
            )
        kw = sc_data['kruskal']
        lines.append(f"  Kruskal-Wallis: H={kw['H']:.3f}  p={kw['p']:.4f}  {kw['sig']}")

    report = "\n".join(lines)
    print("\n" + report)
    path = os.path.join(out_dir, 'stats.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nSaved: results/stats.txt")


def plot_convergence(all_results, algos, out_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    scenarios = list(all_results.keys())
    n = len(scenarios)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4))
    if n == 1:
        axes = [axes]
    colors = {'GA': '#e74c3c', 'Hybrid': '#2980b9'}

    for ax, sc_label in zip(axes, scenarios):
        sc = all_results[sc_label]
        g_score = sc['Greedy']['score_stats']['mean']
        for algo in ['GA', 'Hybrid']:
            hist = sc[algo].get('avg_history', [])
            if hist:
                ax.plot(hist, label=algo, color=colors[algo], lw=1.8)
        ax.axhline(g_score, color='#27ae60', ls='--', lw=1.4,
                   label=f'Greedy ({g_score:.1f})')
        ax.set_title(sc_label.replace('_', ' '), fontsize=9, fontweight='bold')
        ax.set_xlabel('Generation', fontsize=8)
        ax.set_ylabel('Fitness (Score)', fontsize=8)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    fig.suptitle('Convergence — GA vs Hybrid vs Greedy Baseline',
                 fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'convergence.png'), dpi=150, bbox_inches='tight')
    plt.close()


def print_summary(all_results, algos):
    print(f"\n{'=' * 55}")
    print(f"{'Scenario':<25} {'Best':^8} {'Score':>8} {'vs Greedy':>10}")
    print("-" * 53)
    for sc_label, sc_data in all_results.items():
        g_score = sc_data['Greedy']['score_stats']['mean']
        best_algo, best_score = 'Greedy', g_score
        for algo in ['GA', 'Hybrid']:
            s = sc_data[algo]['score_stats']['mean']
            if s > best_score:
                best_score, best_algo = s, algo
        delta = best_score - g_score
        print(f"{sc_label:<25} {best_algo:^8} {best_score:>8.1f} "
              f"{'+' if delta >= 0 else ''}{delta:>9.1f}")


if __name__ == '__main__':
    main()
