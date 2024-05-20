import pandas as pd
import time
import copy
from model import coverage
from node import utils


class Node:

    def __init__(self, uid, pois, scale, detour_radius, ageing):
        self.uid = uid
        self.POIs = pois
        self.scale = scale
        self.ageing = ageing
        self.detour_radius = detour_radius
        self.log = []
        self.merge_log = []  # Keeps track of the data exchange with other nodes
        self.cov_count = 0
        self.coverage = pd.DataFrame(columns=["probability"])
        self.backup_coverages = []
        self.current_trajectory = pd.DataFrame(columns=["lat", "lon", "tid"])
        self.adjacency = {}
        self.recent_exchanges = []
        self.ageing_start = {}

    def move(self, lat, lon, tid, bid):
        if self.current_trajectory.size != 0:

            if self.current_trajectory.loc[0].tid != tid:
                print("--> Computing node coverage map")
                start_coverage = time.perf_counter()
                self.compute_coverage_map(bid)
                end_coverage = time.perf_counter()
                self.log.append((self.uid, end_coverage - start_coverage))
                print(f"--> Coverage map computed in {end_coverage - start_coverage:0.4f}")

                # forse togliere
                # self.trajectories.append(self.current_trajectory)

                self.current_trajectory = pd.DataFrame(columns=["lat", "lon", "tid"])

            self.current_trajectory.loc[len(self.current_trajectory)] = [lat, lon, tid]

        else:
            self.current_trajectory.loc[0] = [lat, lon, tid]

    def compute_coverage_map(self, bid):

        self.do_age_coverage(bid)

        for index, location in self.POIs.iterrows():

            d = min(
                coverage.haversine(location.lat,
                                   location.lon,
                                   self.current_trajectory['lat'].values,
                                   self.current_trajectory['lon'].values
                                   )
            )

            if d <= self.detour_radius:
                coverage_probability = coverage.calculate_coverage(d, self.scale)
            else:
                coverage_probability = 0.0

            if location.id_location in self.coverage.index:
                self.coverage.loc[location.id_location] = [
                    utils.probability_union(self.coverage.loc[location.id_location][0], coverage_probability)]

            else:
                self.coverage = self.coverage.append(
                    pd.DataFrame(coverage_probability, columns=["probability"],
                                 index=[location.id_location]))

            print("Coverage for location {} and node {} calculated successfully with value: {}".format(
                location.id_location,
                self.uid,
                self.coverage.loc[location.id_location].probability)
            )

            if location.id_location in self.ageing_start.keys():
                if coverage_probability > 0:
                    self.ageing_start[index] = bid
            else:
                self.ageing_start[location.id_location] = bid

        # SAVE COPY OF EVERY COVERAGE MAP
        cov_copy = self.coverage.copy()
        cov_copy['copy_id'] = self.cov_count
        cov_copy['bid'] = bid
        self.backup_coverages.append(cov_copy)
        self.cov_count += 1

        # RESTORE RECENT EXCHANGES LIST
        self.recent_exchanges = []

    def do_age_coverage(self, bid):

        for location in self.coverage.index:

            if self.coverage.loc[location][0] != 0:
                ageing_percentage = utils.power_law(start=self.ageing_start[location], current=bid)

                if ageing_percentage < 1:
                    self.ageing_start[location] = bid
                    self.coverage.loc[location] = self.coverage.loc[location] * ageing_percentage

    def merge_coverage(self, bid):

        if self.ageing:
            self.do_age_coverage(bid)

        for node in self.adjacency.keys():

            if node not in self.recent_exchanges:

                # merge current coverage map with all the nodes of the adjacency list and remove current node from the in o
                # order to ovid multiple, useless, merge operations
                if self.ageing:
                    self.adjacency[node].do_age_coverage(bid)

                cov, ageing = utils.merge(self.coverage, self.adjacency[node].coverage, self.ageing_start,
                                          self.adjacency[node].ageing_start)
                self.coverage = cov.copy()
                self.adjacency[node].coverage = cov
                self.ageing_start = copy.deepcopy(ageing)
                self.adjacency[node].ageing_start = ageing

                # Since at every time bucket the position of a node is the result of an average of the points of its trajectory,
                # it could be possible that a node x has another node y in his adjacency list but not vice versa
                try:
                    self.adjacency[node].recent_exchanges.append(self.uid)
                    del self.adjacency[node].adjacency[self.uid]
                except KeyError:
                    continue
                finally:
                    self.recent_exchanges.append(node)
                    self.merge_log.append((self.uid, node, bid))

        self.adjacency = {}
