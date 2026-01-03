import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import colors as mcolors
from pathlib import Path

def lighten(c, factor=0.40):
    r, g, b = mcolors.to_rgb(c)
    return (1 - (1 - r) * (1 - factor), 1 - (1 - g) * (1 - factor), 1 - (1 - b) * (1 - factor))

def redraw_from_results(json_path='experiment_results.json', save_dir=None):
    rp = json_path
    if not os.path.exists(rp):
        pr = Path(os.getenv('PROJECT_ROOT', os.getcwd())).resolve()
        candidates = [rp, str(Path(rp).expanduser()), str(pr / rp), str(pr / 'figs' / rp)]
        for c in candidates:
            if os.path.exists(c):
                rp = c
                break
    if not os.path.exists(rp):
        return
    with open(rp, 'r') as f:
        loaded = json.load(f)
    df = pd.DataFrame(loaded)
    if df.empty:
        return
    sns.set_theme(style='white')
    sns.set_context('talk', font_scale=1.6)
    plt.rcParams.update({
        'figure.dpi': 160,
        'axes.titlesize': 18,
        'axes.titleweight': 'bold',
        'axes.labelsize': 14,
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
        'legend.title_fontsize': 12,
        'legend.fontsize': 12,
        'axes.linewidth': 1.2,
        'lines.linewidth': 2.0,
        'patch.linewidth': 0.8,
        'grid.linewidth': 0.8,
    })
    base_palette = {'M1': '#4E79A7', 'M2': '#F28E2B', 'M3': '#59A14F'}
    few_palette = {k: lighten(v, 0.40) for k, v in base_palette.items()}
    modes = ['Zero', 'Few']
    agg = df.groupby(['Method', 'Mode']).agg(
        Accuracy=('is_correct', 'mean'),
        Avg_Rounds=('rounds', 'mean'),
        SyntaxFixCount=('syntax_fix', 'sum')
    ).reset_index()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Performance Overview', fontsize=18, fontweight='bold')
    for i, mode in enumerate(modes):
        ax_acc = axes[0, i]
        subset = agg[agg['Mode'] == mode]
        sns.barplot(data=subset, x='Method', y='Accuracy', palette=base_palette, ax=ax_acc)
        ax_acc.set_title(f'Accuracy ({mode}-Shot)')
        ax_acc.set_ylim(0, 1)
        ax_acc.grid(True, axis='y', linestyle='--', alpha=0.5)
        ax_rds = axes[1, i]
        sns.barplot(data=subset, x='Method', y='Avg_Rounds', palette=base_palette, ax=ax_rds)
        ax_rds.set_title(f'Avg Rounds ({mode}-Shot)')
        ax_rds.grid(True, axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        out_path = str(Path(save_dir) / 'overview.png')
        plt.savefig(out_path)
    plt.show()

