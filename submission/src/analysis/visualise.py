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


def plot_heatmap(grouped_by_node, name):
    n_cols = 7
    n_rows = 7
    layout = [[0 for col in range(0, n_cols)] for row in range(0, n_rows)]

    snapshots = [copy.deepcopy(layout) for x in range(n_snapshots)]

    for node_id, group in grouped_by_node:
        for idx, row in group.iterrows():
            snapshot_index = get_snapshot_index(row.sent_at_time, bins)
            map_row, map_col = index_dict[node_id]
            snapshots[snapshot_index][map_row][map_col] = snapshots[snapshot_index][map_row][map_col] + 1

    for idx, snapshot in enumerate(snapshots):
        if idx == len(bins) - 1:
            # Last bin has single value, not really useful
            continue

        fig, ax = plt.subplots()
        fig.suptitle("{} traffic during snapshot {}".format(name, idx))
        ax.set_xticks([])
        ax.set_yticks([])
        im = ax.imshow(snapshots[idx], interpolation="nearest")
        fig.colorbar(im)

        # Label with node ID and number of packets sent
        for i in range(len(layout)):
            for j in range(len(layout)):
                if (i, j) in index_dict.values():
                    id = {id for id, coords in index_dict.items() if coords == (i, j)}.pop()
                    text = ax.text(j, i, "ID {}".format(id), ha="center", va="center", color="w")

        fig.savefig("snapshot{}-{}.png".format(idx, name))


ap = argparse.ArgumentParser()
ap.add_argument("data_file", help="CSV file containing experiment data", type=str)
ap.add_argument("sink_file", help="CSV file containing readings received by sink node", type=str)

args = ap.parse_args()

data = pd.read_csv(args.data_file)
sink = pd.read_csv(args.sink_file)

# Read failed at time and remove last row from sink reading
failed_at_time = sink.tail(1).values[0][0]
sink = sink[:-1]
print(failed_at_time)

# Remove any packets sent after the sink failed
data = data[data.sent_at_time < failed_at_time]
# Remove packets sent by sink
data = data.query('node_id != 21')
data_packets = data.query('packet_type == "data"')
control_packets = data.query('packet_type == "control"')

start_time = data["sent_at_time"].min()
end_time = data["sent_at_time"].max()

n_snapshots = 4
bins = np.linspace(start_time, end_time, n_snapshots)

data_grouped_by_node = data.groupby("node_id")
control_grouped_by_node = control_packets.groupby("node_id")

index_dict = {
    1: (0, 0),
    2: (0, 2),
    3: (1, 1),
    4: (2, 0),
    5: (2, 2),
    6: (0, 4),
    7: (0, 6),
    8: (1, 5),
    9: (2, 4),
    10: (2, 6),
    11: (4, 0),
    12: (4, 2),
    13: (5, 1),
    14: (6, 0),
    15: (6, 2),
    16: (4, 4),
    17: (4, 6),
    18: (5, 5),
    19: (6, 4),
    20: (6, 6),
}

plot_heatmap(data_grouped_by_node, "Data")
plot_heatmap(control_grouped_by_node, "Control")
