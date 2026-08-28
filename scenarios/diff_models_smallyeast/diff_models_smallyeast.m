function results = diff_models_smallyeast(ctx)
% MATLAB side of the model-diffing scenario.
%
% diffModels returns report.equal and report.differences --- a cell array of
% human-readable strings phrased however this implementation likes. The
% strings themselves are not compared; only the count is, which both sides
% increment once per difference found. See run.py and scenario.yml for why.
%
% reactions_only_in_a/b and genes_only_in_a/b are derived directly from the
% two models rather than from diffModels' own rxnsOnlyInA-style fields: that
% would test the fixture, not the function, and this scenario keeps the two
% separate on purpose.

inputs = ctx.inputs;

a = readYAMLmodel(inputs.model);
a = set_eccode(a, char(inputs.eccode.reaction), char(inputs.eccode.a));
b = modified(inputs);

report = diffModels(a, b);

results.modified.equal = logical(report.equal);
results.modified.n_differences = numel(report.differences);
results.modified.reactions_only_in_a = sort_cellstr(setdiff(a.rxns, b.rxns));
results.modified.reactions_only_in_b = sort_cellstr(setdiff(b.rxns, a.rxns));
results.modified.genes_only_in_a = sort_cellstr(setdiff(a.genes, b.genes));
results.modified.genes_only_in_b = sort_cellstr(setdiff(b.genes, a.genes));

% Two independent, otherwise-untouched reads of the same file: a cheap
% determinism check that the reader and the diff function together introduce
% no artefact of their own. Deliberately not the annotated `a` above, which
% would show the ec-code edit as a spurious difference.
selfReport = diffModels(readYAMLmodel(inputs.model), readYAMLmodel(inputs.model));
results.self.equal = logical(selfReport.equal);
results.self.n_differences = numel(selfReport.differences);

end


function model = modified(inputs)
model = readYAMLmodel(inputs.model);

model = removeReactions(model, {char(inputs.removed_reaction)});

added = inputs.added_reaction;
rxnsToAdd.rxns = {char(added.id)};
rxnsToAdd.equations = {char(added.equation)};
rxnsToAdd.rxnNames = {char(added.name)};
model = addRxns(model, rxnsToAdd, 'eqnType', 1, 'allowNewMets', false, 'allowNewGenes', false);

stoich = inputs.stoichiometry;
model = changeRxns(model, {char(stoich.reaction)}, {char(stoich.equation)}, ...
    'eqnType', 1, 'allowNewMets', false);

bounds = inputs.bounds;
i = find(strcmp(model.rxns, char(bounds.reaction)), 1);
model.ub(i) = double(bounds.upper_bound);

objective = inputs.objective;
i = find(strcmp(model.rxns, char(objective.reaction)), 1);
model.c(i) = double(objective.coefficient);

changed = inputs.gpr_changed;
model = changeGrRules(model, {char(changed.reaction)}, {char(changed.grRule)}, 'replace', true);

reordered = inputs.gpr_reordered;
model = changeGrRules(model, {char(reordered.reaction)}, {char(reordered.grRule)}, 'replace', true);

eccode = inputs.eccode;
model = set_eccode(model, char(eccode.reaction), char(eccode.b));

formula = inputs.metabolite_formula;
i = find(strcmp(model.mets, char(formula.metabolite)), 1);
model.metFormulas{i} = char(formula.b);

charge = inputs.metabolite_charge;
i = find(strcmp(model.mets, char(charge.metabolite)), 1);
% metCharges is absent entirely on a fresh read when nothing in the file
% declares a charge (true of every metabolite here) --- a bare indexed
% assignment into a field that does not exist yet would auto-vivify it
% zero-filled rather than NaN-filled, silently giving every other
% metabolite a charge of 0 instead of leaving it unset.
if ~isfield(model, 'metCharges')
    model.metCharges = nan(numel(model.mets), 1);
end
model.metCharges(i) = double(charge.b);
end


function model = set_eccode(model, rxnId, value)
% RAVEN's eccodes is a plain cellstr, one entry per reaction, with no
% structured annotation map the way cobra's reaction.annotation is --- so
% setting the one field diffModels itself reads is a direct string
% assignment here, where the Python side sets a dict key.
if ~isfield(model, 'eccodes')
    model.eccodes = repmat({''}, numel(model.rxns), 1);
end
i = find(strcmp(model.rxns, rxnId), 1);
model.eccodes{i} = value;
end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end
