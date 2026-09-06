function results = fit_parameters_toy(ctx) %#ok<INUSD>
% MATLAB side of the fitParameters/fit_parameters toy-model scenario.
%
% No shared fixture file: the model (A -> RA -> x, B -> RB -> x, k*x ->
% GROWTH) is small enough to build directly here, identically to run.py's
% _chain_model(). See scenario.yml for why two input reactions (not one)
% are needed to exercise SysBioChalmers/RAVEN#742's fix, and why the
% expected fit is analytically exact rather than solver-dependent.

model = chainModel();

xRxns = {'EX_A';'EX_B'};
xValues = [2 4; 4 2; 6 6];       % rows are data points, columns are A, B
rxnsToFit = {'GROWTH'};
valuesToFit = [3; 3; 6];         % true k=2: (a+b)/2

xIdx = find(strcmp(model.mets,'x'));
gIdx = find(strcmp(model.rxns,'GROWTH'));
parameterPositions.position = {sub2ind(size(model.S), xIdx, gIdx)};
parameterPositions.isNegative = {true};

[parameters, fitnessScore, ~, newModel] = fitParameters(model, xRxns, xValues, ...
    rxnsToFit, valuesToFit, parameterPositions, 'initialGuess', 1, 'plotFitting', true);

results.parameters = parameters;
results.fitness_score = fitnessScore;
fittedX = find(strcmp(newModel.mets,'x'));
fittedGrowth = find(strcmp(newModel.rxns,'GROWTH'));
results.fitted_coefficient = full(newModel.S(fittedX, fittedGrowth));
end


function model = chainModel()
model.id = 'fit_toy';
model.name = 'fit_toy';
model.mets = {'a';'b';'x'};
model.metNames = model.mets;
model.metComps = ones(3,1);
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'EX_A';'EX_B';'RA';'RB';'GROWTH'};
model.rxnNames = model.rxns;
%       EX_A EX_B RA  RB  GROWTH
model.S = sparse([
     1    0   -1   0    0;    % a
     0    1    0  -1    0;    % b
     0    0    1   1   -1]);  % x  (GROWTH coefficient is a placeholder, overwritten by fitParameters)
model.lb = zeros(5,1);
model.ub = repmat(1000,5,1);
model.rev = zeros(5,1);
model.c = zeros(5,1);
model.b = zeros(3,1);
end
