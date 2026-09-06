function results = guess_composition_toy(ctx) %#ok<INUSD>
% MATLAB side of the guessComposition/guess_composition toy-model scenario.
%
% A -> B -> C chain (A's formula known, B and C unknown), a separate
% A -> 2 D reaction (D's own coefficient is 2), and an orphan metabolite
% with no reactions. See scenario.yml.

model = chainModel();

[newModel, guessedFor, couldNotGuess] = guessComposition(model, 'printResults', false);

results.guessed_for = sort(guessedFor);
results.could_not_guess = sort(couldNotGuess);
results.b_formula = newModel.metFormulas{strcmp(newModel.mets, 'B')};
results.c_formula = newModel.metFormulas{strcmp(newModel.mets, 'C')};
results.d_formula = newModel.metFormulas{strcmp(newModel.mets, 'D')};
end


function model = chainModel()
model.id = 'guess_composition_toy';
model.name = 'guess_composition_toy';
model.mets = {'A'; 'B'; 'C'; 'D'; 'Orphan'};
model.metNames = model.mets;
model.metComps = ones(5, 1);
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.metFormulas = {'CH4'; ''; ''; ''; ''};
model.rxns = {'R1'; 'R2'; 'R3'};
model.rxnNames = model.rxns;
%       R1  R2  R3
model.S = sparse([
    -1   0  -1;    % A
     1  -1   0;    % B
     0   1   0;    % C
     0   0   2;    % D
     0   0   0]);  % Orphan
model.lb = zeros(3, 1);
model.ub = repmat(1000, 3, 1);
model.rev = zeros(3, 1);
model.c = zeros(3, 1);
model.b = zeros(5, 1);
end
