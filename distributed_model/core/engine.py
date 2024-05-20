import yaml
from geopy.distance import distance
import pandas as pd
import time
import csv
from node.node import Node
from pathlib import Path

global conf

log = []
nodes = {}
time_buckets = []
ROOT = Path().resolve().parent


def initialize(path_gps, granularity=None, start_date=None, end_date=None, synthetic=False):
    print("Initialization started...")
    print("-> Reading input sources")
    geo = pd.read_csv(path_gps)

    print("-> Filtering geolife")
    if not synthetic:
        geo = geo[geo['uid'] < 3000]
    else:
        # TODO handle big uid in dataset
        pass

    geo['date_time'] = pd.to_datetime(geo['date_time'], errors='coerce')

    if start_date is not None:
        geo = geo[geo['date_time'] >= start_date]
    if end_date is not None:
        geo = geo[geo['date_time'] <= end_date]

    if granularity == "min":
        geo['date_time'] = geo['date_time'].dt.floor('min')
    if granularity == "h":
        geo['date_time'] = geo['date_time'].dt.floor('h')

    geo = geo.groupby(['date_time', 'uid'], as_index=False).mean()

    for time in geo['date_time'].unique():
        time_buckets.append(geo[geo['date_time'] == time])

    print("Initialization ended.")


def start_simulation(path_pois):
    print("Reading POIs...")
    pois = pd.read_csv(path_pois)

    print("Starting simultation...")
    counter = 1
    for bucket in time_buckets:
        print(
            "-> Analyzing bucket {}/{}: {}".format(counter, len(time_buckets), bucket['date_time'].values[0]))
        start_bucket = time.perf_counter()

        inner_counter = 1
        for c_index, current_node in bucket.iterrows():
            print("--> Processing node {} of {}".format(inner_counter, len(bucket)))
            inner_counter += 1

            skip = False
            if current_node.uid not in nodes.keys():
                ageing = conf["ageing_active"]
                nodes[current_node.uid] = Node(current_node.uid, pois, conf["SCALE"], conf["DETOUR_RADIUS"], ageing)
                nodes[current_node.uid].move(lat=current_node.lat, lon=current_node.lon, tid=current_node.tid,
                                             bid=bucket['date_time'].values[0])
            else:
                nodes[current_node.uid].move(lat=current_node.lat, lon=current_node.lon, tid=current_node.tid,bid=bucket['date_time'].values[0])
            skip = True

            if conf["ADJACENCY_THRESHOLD"] > 0:
                print("--> Computing nodes adjacency")
                start_adjacency = time.perf_counter()
                for neighbor in nodes.keys() - [current_node.uid]:
                    # Calculate distance between two nodes
                    d = distance((float(nodes[current_node.uid].current_trajectory.tail(1).lat),
                                  float(nodes[current_node.uid].current_trajectory.tail(1).lon)),
                                 (float(nodes[neighbor].current_trajectory.tail(1).lat),
                                  float(nodes[neighbor].current_trajectory.tail(1).lon)))
                    if d.meters <= conf['ADJACENCY_THRESHOLD'] and not d.meters == 0:
                        nodes[current_node.uid].adjacency[neighbor] = nodes[neighbor]

                end_adjacency = time.perf_counter()
                print(f"--> Node adjacency computed in {end_adjacency - start_adjacency:0.4f}")
                log.append((bucket['date_time'].values[0], "adjacency", end_adjacency - start_adjacency))

            if not skip:
                nodes[current_node.uid].move(lat=current_node.lat, lon=current_node.lon,
                                             tid=current_node.tid, bid=bucket['date_time'].values[0])

        end_bucket = time.perf_counter()
        print("-> Bucket analyzed in {}".format(end_bucket - start_bucket))

        print("-> Merging coverages map") if len(nodes.keys()) > 0 else print("-> No merge")
        start_merging = time.perf_counter()
        for node in nodes.keys():
            if nodes[node].adjacency != {}:
                nodes[node].merge_coverage(bid=bucket['date_time'].values[0])
        end_merging = time.perf_counter()
        log.append((bucket['date_time'].values[0], "merge", end_merging - start_merging))
        print(f"-> Merge procedure completed in {end_merging - start_merging:0.4f}\n")
        counter += 1


def finalize_simulation():
    bid = time_buckets[-1]['date_time'].values[0]
    for node in nodes.keys():
        nodes[node].compute_coverage_map(bid=bid)

    for node in nodes.keys():
        start_merging = time.perf_counter()
        nodes[node].merge_coverage(bid=bid)
        end_merging = time.perf_counter()
        log.append(("", "merge", end_merging - start_merging))

    for node in nodes.keys():
        pd.concat(nodes[node].backup_coverages).to_csv(f"{ROOT}/{conf['out_path']}cov_series/{node}_coverages.csv")


def save_results(path):
    print("Collecting coverages...")
    res = []
    logs = []
    merge_logs = []
    for node in nodes.keys():
        df_node_with_uid = pd.DataFrame()
        df_node_with_uid['uid'] = [node] * len(nodes[node].coverage)
        df_node_with_uid['id_location'] = nodes[node].coverage.index
        df_node_with_uid['probability'] = nodes[node].coverage.probability.values

        res.append(df_node_with_uid)
        logs += nodes[node].log
        merge_logs += nodes[node].merge_log

    print("Saving results...")
    pd.concat(res).to_csv("{}/coverage.csv".format(path))

    with open(f'{path}/log_coverage.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['node', 'time'])
        for row in logs:
            csv_out.writerow(row)

    with open(f'{path}/log_merge.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['node_1', 'node_2', 'bid'])
        for row in merge_logs:
            csv_out.writerow(row)


if __name__ == "__main__":

    with open("conf.yml") as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

    Path(f"{ROOT}/{conf['out_path']}/cov_series").mkdir(parents=True, exist_ok=True)

    initialize(path_gps=f"{ROOT}/{conf['path_gps']}",
               granularity=conf['granularity'],
               start_date=conf['start_date'], end_date=conf['end_date'])
    start_simulation(path_pois=f"{ROOT}/{conf['path_pois']}")
    finalize_simulation()
    save_results(path=f"{ROOT}/{conf['out_path']}")

    with open(f"{ROOT}/{conf['out_path']}/log_engine.csv", 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['bucket', 'type', 'time'])
        for row in log:
            csv_out.writerow(row)
