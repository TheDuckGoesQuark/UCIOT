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

n_snapshots = 3
bins = np.linspace(start_time, end_time, n_snapshots)

grouped_by_node = data.groupby("node_id")

n_cols = 4
n_rows = 4
layout = [[0 for col in range(0, n_cols)] for row in range(0, n_rows)]

snapshots = [layout.copy() for x in range(n_snapshots)]

for node_id, group in grouped_by_node:
    if node_id == 17:
        continue
    for idx, row in group.iterrows():
        snapshot_index = get_snapshot_index(row.sent_at_time, bins)
        heatmap_row = int((node_id - 1) / 4)
        heatmap_col = (node_id - 1) % 4
        snapshots[snapshot_index][heatmap_row][heatmap_col] = snapshots[snapshot_index][heatmap_row][heatmap_col] + 1

for idx, snapshot in enumerate(snapshots):
    fig, ax = plt.subplots()
    im = ax.imshow(snapshots[idx])
    ax.set_title("Packets sent during snapshot {}".format(idx + 1))
    fig.colorbar(im)

    # Label with node ID
    for i in range(len(layout)):
        for j in range(len(layout)):
            text = ax.text(j, i, "ID {}\nSENT {}".format((i * 4 + j) + 1, snapshot[i][j]),
                           ha="center", va="center", color="w")

    fig.show()
