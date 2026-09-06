function results = differential_sampling_toy(ctx) %#ok<INUSD>
% MATLAB side of the getFluxZ/analyzeSampling toy scenario.
%
% No model needed: both functions work on plain reactions x samples
% matrices. See scenario.yml for what each row isolates.

zA = [ ...
    1 2 3;      % R1: general formula
    5 5 5;      % R2: zero-variance increase
    9 9 9;      % R3: zero-variance decrease (SysBioChalmers/RAVEN#742)
    1 2 3;      % R4: equal means, nonzero variance
    2 2 2;      % R5: equal means, zero variance
    0 0 1e-6];  % R6: clamped to +-100
zB = [ ...
    3 4 5;      % R1
    9 9 9;      % R2
    5 5 5;      % R3
    1 2 3;      % R4
    2 2 2;      % R5
    1000 1000 1000+1e-6]; % R6

results.flux_z = getFluxZ(zA, zB);

sA = [ ...
    1 1 1;      % S1: concordant
    1 1 1;      % S2: discordant
    -5 -5 -5];  % S3: sign-flip then concordant
sB = [ ...
    5 5 5;
    5 5 5;
    -9 -9 -9];
tex = [3; -3; 3];
df = 10;

evalc('scores = analyzeSampling(tex, df, sA, sB);');
% num2cell(scores,2), not the bare matrix: a plain MxN double serializes to
% JSON flattened column-major, not as nested per-row arrays.
results.analyze_sampling = num2cell(scores, 2);
end
