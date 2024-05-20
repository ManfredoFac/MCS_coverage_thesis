import yaml
import pandas as pd
from pathlib import Path

ROOT = Path().resolve()

with open(f"{ROOT}/conf.yml") as f:
    conf = yaml.load(f, Loader=yaml.FullLoader)


def probability_union(p1, p2):
    # P(AUB) = P(A) + P(B) - P(A)*P(B)
    return 1 - (1 - p1) * (1 - p2)


def merge(cov1, cov2, ageing1, ageing2):
    for index, row in cov1.iterrows():

        if index in cov2.index:

            cov2.at[index] = probability_union(row.probability, cov2.at[index, 'probability'])
            ageing2[index] = max(ageing2[index], ageing1[index])

        else:
            cov2 = cov2.append(pd.DataFrame(row.probability, columns=["probability"],
                                            index=[index]))
            ageing2[index] = ageing1[index]

    return cov2, ageing2


def power_law(start, current):
    days = int(current - start) / 1000000000 / 60 / 60 / 24

    if days == 0:
        return 1

    res = conf['powerlaw_a_param'] * pow(days, conf['powerlaw_k_param'])

    if res >= 1:
        return 1
    else:
        return res


