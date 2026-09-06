"""Python side of the getFluxZ/analyzeSampling toy scenario."""
import pandas as pd

from raven_toolbox.analysis import analyze_sampling, get_flux_z


def run(ctx):
    z_a = pd.DataFrame(
        {
            "R1": [1.0, 2.0, 3.0],
            "R2": [5.0, 5.0, 5.0],
            "R3": [9.0, 9.0, 9.0],
            "R4": [1.0, 2.0, 3.0],
            "R5": [2.0, 2.0, 2.0],
            "R6": [0.0, 0.0, 1e-6],
        }
    )
    z_b = pd.DataFrame(
        {
            "R1": [3.0, 4.0, 5.0],
            "R2": [9.0, 9.0, 9.0],
            "R3": [5.0, 5.0, 5.0],
            "R4": [1.0, 2.0, 3.0],
            "R5": [2.0, 2.0, 2.0],
            "R6": [1000.0, 1000.0, 1000.0 + 1e-6],
        }
    )
    flux_z = get_flux_z(z_a, z_b)

    s_a = pd.DataFrame({"S1": [1.0, 1.0, 1.0], "S2": [1.0, 1.0, 1.0], "S3": [-5.0, -5.0, -5.0]})
    s_b = pd.DataFrame({"S1": [5.0, 5.0, 5.0], "S2": [5.0, 5.0, 5.0], "S3": [-9.0, -9.0, -9.0]})
    tex = [3.0, -3.0, 3.0]
    df = 10
    scores = analyze_sampling(tex, df, s_a, s_b)

    return {
        "flux_z": [flux_z[rid] for rid in ["R1", "R2", "R3", "R4", "R5", "R6"]],
        "analyze_sampling": scores.loc[["S1", "S2", "S3"]].to_numpy().tolist(),
    }
