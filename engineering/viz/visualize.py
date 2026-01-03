import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def visualize_results(res_m1_zero, res_m1_few, res_m2_zero, res_m2_few, res_m3_zero, res_m3_few, test_subset=None):
    data_map = {
        'M1_Zero': res_m1_zero, 'M1_Few': res_m1_few,
        'M2_Zero': res_m2_zero, 'M2_Few': res_m2_few,
        'M3_Zero': res_m3_zero, 'M3_Few': res_m3_few
    }
    json_data = []
    for key, df in data_map.items():
        if df.empty:
            continue
        method, mode = key.split('_')
        records = df.to_dict(orient='records')
        for r in records:
            r['Method'] = method
            r['Mode'] = mode
            if r['is_correct']:
                if r.get('syntax_fix', False):
                    r['Status'] = 'Syntax Fix Correct'
                elif r.get('rounds', 0) == 0:
                    r['Status'] = 'Initial Correct'
                else:
                    r['Status'] = 'Interactive Correct'
            else:
                r['Status'] = 'Incorrect'
        json_data.extend(records)
    json_path = 'experiment_results.json'
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    with open(json_path, 'r') as f:
        loaded_data = json.load(f)
    full_df = pd.DataFrame(loaded_data)
    if full_df.empty:
        return
    sns.set_theme(style="white")
    sns.set_context("paper", font_scale=1.2)
    palette_dict = {'M1': '#4E79A7', 'M2': '#F28E2B', 'M3': '#59A14F'}
    fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
    fig1.suptitle('Performance Overview', fontsize=16, fontweight='bold')
    modes = ['Zero', 'Few']
    agg_df = full_df.groupby(['Method', 'Mode']).agg(
        Accuracy=('is_correct', 'mean'),
        Avg_Rounds=('rounds', 'mean')
    ).reset_index()
    for i, mode in enumerate(modes):
        ax_acc = axes1[0, i]
        subset = agg_df[agg_df['Mode'] == mode]
        sns.barplot(data=subset, x='Method', y='Accuracy', palette=palette_dict, ax=ax_acc)
        ax_acc.set_title(f'Accuracy ({mode}-Shot)')
        ax_acc.set_ylim(0, 1)
        ax_acc.grid(True, axis='y', linestyle='--', alpha=0.5)
        ax_rds = axes1[1, i]
        sns.barplot(data=subset, x='Method', y='Avg_Rounds', palette=palette_dict, ax=ax_rds)
        ax_rds.set_title(f'Avg Rounds ({mode}-Shot)')
        ax_rds.grid(True, axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()
    if test_subset is not None and 'difficulty' in test_subset.columns:
        plt.figure(figsize=(6, 6))
        diff_counts = test_subset['difficulty'].value_counts()
        colors_map = {'Hard': '#ff9999', 'Medium': '#ffff99', 'Simple': '#66b3ff'}
        pie_colors = [colors_map.get(l, '#cccccc') for l in diff_counts.index]
        plt.pie(diff_counts, labels=diff_counts.index, autopct='%1.1f%%', startangle=140, colors=pie_colors)
        plt.title('Test Sample Difficulty Distribution', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.show()

