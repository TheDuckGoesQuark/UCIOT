import copy

import pandas as pd
import argparse
import numpy as np
import matplotlib.pyplot as plt


def get_snapshot_index(time_value, snapshot_start_times):
    for idx in range(len(snapshot_start_times) - 1, 0, -1):
        if time_value >= snapshot_start_times[idx]:
            return idx

    return 0


ap = argparse.ArgumentParser()
ap.add_argument("data_file", help="CSV file containing experiment data")

args = ap.parse_args()

data = pd.read_csv(args.data_file)

start_time = data["sent_at_time"].min()
end_time = data["sent_at_time"].max()

n_snapshots = 4
bins = np.linspace(start_time, end_time, n_snapshots)

grouped_by_node = data.groupby("node_id")

n_cols = 4
n_rows = 4
layout = [[0 for col in range(0, n_cols)] for row in range(0, n_rows)]

snapshots = [copy.deepcopy(layout) for x in range(n_snapshots)]

for node_id, group in grouped_by_node:
    if node_id == 17:
        continue
    for idx, row in group.iterrows():
        snapshot_index = get_snapshot_index(row.sent_at_time, bins)
        heatmap_row = int((node_id - 1) / 4)
        heatmap_col = (node_id - 1) % 4
        snapshots[snapshot_index][heatmap_row][heatmap_col] = snapshots[snapshot_index][heatmap_row][heatmap_col] + 1

for idx, snapshot in enumerate(snapshots):
    if idx == len(bins) - 1:
        # Last bin has single value, not really useful
        continue

    fig, ax = plt.subplots()
    im = ax.imshow(snapshots[idx], interpolation="nearest")
    if idx == 0:
        duration_str = "{0:.2f}s - {0:.2f}s".format(bins[0] - start_time, bins[idx + 1] - start_time)
    elif idx < len(bins) - 1:
        duration_str = "{0:.2f}s - {0:.2f}s".format(bins[idx] - start_time, bins[idx + 1] - start_time)
    else:
        duration_str = "{0:.2f}s - {0:.2f}s".format(bins[idx] - start_time, end_time - start_time)

    ax.set_title("Packets sent between {}".format(duration_str))
    fig.colorbar(im)

    # Label with node ID and number of packets sent
    for i in range(len(layout)):
        for j in range(len(layout)):
            text = ax.text(j, i, "ID {}\n{}".format((i * 4 + j) + 1, snapshot[i][j]),
                           ha="center", va="center", color="w")

    fig.savefig("snapshot{}.png".format(idx))
