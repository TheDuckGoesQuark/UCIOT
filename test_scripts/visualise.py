import pandas as pd
import argparse
import numpy as np
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("data_file", help="CSV file containing experiment data")

args = ap.parse_args()

data = pd.read_csv(args.data_file)

start_time = data["sent_at_time"].min()
end_time = data["sent_at_time"].max()

snapshots = np.linspace(start_time, end_time, 3)

data["binned"] = pd.cut(data["sent_at_time"], snapshots)
layout = [[x for x in range(y, y + 4)] for y in range(1, 17, 4)]
print(layout)

fig, ax = plt.subplots()
im = ax.imshow(layout)

fig.tight_layout()
plt.show()
