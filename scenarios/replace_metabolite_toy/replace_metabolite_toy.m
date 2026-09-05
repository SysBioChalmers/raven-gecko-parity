function results = replace_metabolite_toy(ctx)
% MATLAB side of the replaceMets/replace_metabolite toy-model scenario.
% Calls the real replaceMets directly (it transforms and returns the
% model, unlike walkFluxes/followChanged).

nameModel = name_based_model();
evalc('nameModel = replaceMets(nameModel, ctx.inputs.name_based.metabolite, ctx.inputs.name_based.replacement);');
results.name_based = checkpoint(nameModel);

idModel = identifiers_model();
evalc('idModel = replaceMets(idModel, ctx.inputs.identifiers_based.metabolite, ctx.inputs.identifiers_based.replacement, ''identifiers'', true);');
results.identifiers_based = checkpoint(idModel);
end


function model = name_based_model()
model.mets = {'a';'b';'x';'d'};
model.metNames = {'oxygen';'o2';'x';'d'};
model.metComps = [1;1;1;1];
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'r1';'r2';'unrelated1';'unrelated2'};
model.rxnNames = model.rxns;
model.S = sparse([-1 0 0 0; 0 -1 0 0; 1 1 0 0; 0 0 -1 -1]);
model.lb = [-1000;-1000;-1000;-1000];
model.ub = [1000;1000;1000;1000];
model.rev = [1;1;1;1];
model.c = [0;0;0;0];
model.b = zeros(4,1);
end


function model = identifiers_model()
model.mets = {'a';'b';'x'};
model.metNames = {'oxygen';'o2';'x'};
model.metComps = [1;1;1];
model.comps = {'c'};
model.compNames = {'cytoplasm'};
model.rxns = {'r1'};
model.rxnNames = {'r1'};
model.S = sparse([-1;0;1]);
model.lb = -1000;
model.ub = 1000;
model.rev = 1;
model.c = 0;
model.b = zeros(3,1);
end


function out = checkpoint(model)
[~, order] = sort(model.mets);
mets = {};
for i = 1:numel(order)
    idx = order(i);
    row.id = model.mets{idx};
    row.name = model.metNames{idx};
    row.compartment = model.comps{model.metComps(idx)};
    mets{end+1} = row; %#ok<AGROW>
end
out.metabolites = mets;

reactions = struct();
for i = 1:numel(model.rxns)
    col = full(model.S(:, i));
    nz = find(col ~= 0);
    [~, ord2] = sort(model.mets(nz));
    nz = nz(ord2);
    entries = {};
    for j = 1:numel(nz)
        e.metabolite = model.mets{nz(j)};
        e.coefficient = col(nz(j));
        entries{end+1} = e; %#ok<AGROW>
    end
    reactions.(model.rxns{i}) = entries;
end
out.reactions = reactions;
end
