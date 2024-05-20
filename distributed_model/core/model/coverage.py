import scipy.integrate as integrate
from scipy.stats import expon
import numpy as np


def convert(s):
    try:
        return float(s)
    except ValueError:
        num, denom = s.split('/')
        return float(num) / float(denom)


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.deg2rad, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    # total_meters = METERS * c
    r = 6371000  # radiu * 1000 to return meters
    return c * r


def calculate_coverage_centr(locations_id, distances, scale):
    coverages = []

    # initialize coverage inner function
    inner = lambda x: expon.pdf(x, scale=scale)
    print("Calculating coverage with scale:", scale)
    counter = 0
    for loc in locations_id:
        print("Processing location,count, tot: ", loc, counter, len(locations_id))
        counter += 1
        dists_location = distances[distances.id_location == loc]
        # if the location has no points whatsoever, assign 0 to the coverage value and continue
        if len(dists_location) == 0:
            coverages.append(0)
            print("no points for location: ", loc)
            continue

        # the list of ids of the users with some points close to the location
        uids = dists_location.uid.unique()
        # users
        w = []
        for user in uids:
            # print(user)
            dists_location_user = dists_location[(dists_location.uid == user)]
            if len(dists_location_user) == 0:
                print("WARNING: no user's points for: ", loc)
                continue
            # Trajectories
            tids = dists_location_user.tid.unique()
            k = []
            for traj in tids:
                dists_location_user_traj = dists_location_user[(dists_location_user.tid == traj)]
                if len(dists_location_user_traj) == 0:
                    print("WARNING: no user trajectories for: ", loc)
                    continue
                # min distance
                min_distance = dists_location_user_traj["distance"].iloc[0]
                y = integrate.quad(inner, min_distance, np.inf)[0]
                k.append(1 - y)
            m = 1 - np.prod(k)
            w.append(1 - m)
        coverages.append(1 - np.prod(w))

    # import pdb; pdb.set_trace()
    return coverages


def calculate_coverage(min_distance, scale):
    # initialize coverage inner function
    return integrate.quad(lambda x: expon.pdf(x, scale=scale), min_distance, np.inf)[0]
