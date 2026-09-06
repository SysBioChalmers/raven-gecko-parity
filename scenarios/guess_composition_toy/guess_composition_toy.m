function results = guess_composition_toy(ctx) %#ok<INUSD>
% MATLAB side of the guessComposition/guess_composition toy-model scenario.
%
% A -> B -> C chain (A's formula known, B and C unknown) plus an orphan
% metabolite with no reactions. See scenario.yml for why every resolving
% coefficient here is +-1.

model = chainModel();

[newModel, guessedFor, couldNotGuess] = guessComposition(model, 'printResults', false);

results.guessed_for = sort(guessedFor);
results.could_not_guess = sort(couldNotGuess);
results.b_formula = newModel.metFormulas{strcmp(newModel.mets, 'B')};
results.c_formula = newModel.metFormulas{strcmp(newModel.mets, 'C')};
end


function model = chainModel()
model.id = 'guess_composition_toy';
model.name = 'guess_composition_toy';
model.mets = {'A'; 'B'; 'C'; 'Orphan'};
model.metNames = model.mets;
model.metComps = ones(4, 1);
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.metFormulas = {'CH4'; ''; ''; ''};
model.rxns = {'R1'; 'R2'};
model.rxnNames = model.rxns;
%       R1  R2
model.S = sparse([
    -1   0;    % A
     1  -1;    % B
     0   1;    % C
     0   0]);  % Orphan
model.lb = zeros(2, 1);
model.ub = repmat(1000, 2, 1);
model.rev = zeros(2, 1);
model.c = zeros(2, 1);
model.b = zeros(4, 1);
end
