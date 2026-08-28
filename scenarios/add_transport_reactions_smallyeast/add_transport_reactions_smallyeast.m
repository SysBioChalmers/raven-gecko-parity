function results = add_transport_reactions_smallyeast(ctx)
% MATLAB side of the transport-reactions scenario.
%
% addTransport and add_transport_reactions take the same three positional
% arguments and the same onlyToExisting default. New reactions are derived by
% difference from the model before and after, matching the convention used
% everywhere else in this suite: addTransport returns only the updated model
% plus the new ids, so the difference is the one quantity both sides can
% state.
%
% Reaction ids are deliberately not compared --- see scenario.yml.

inputs = ctx.inputs;

results.reversible = checkpoint(inputs, true);
results.irreversible = checkpoint(inputs, false);

end


function out = checkpoint(inputs, isRev)
model = readYAMLmodel(inputs.model);
beforeRxns = model.rxns(:);
beforeMets = model.mets(:);

[updated, added] = addTransport(model, char(inputs.from_compartment), ...
    {char(inputs.to_compartment)}, ...
    'metNames', as_cellstr(inputs.metabolite_names), ...
    'isRev', isRev, ...
    'onlyToExisting', true);

afterMets = updated.mets(:);

out.n_reactions_before = numel(beforeRxns);
out.n_reactions_after = numel(updated.rxns);
out.n_added = numel(added);
out.n_metabolites_before = numel(beforeMets);
out.n_metabolites_after = numel(afterMets);

out.transports = transport_records(updated, added, ...
    char(inputs.from_compartment), char(inputs.to_compartment));
end


function records = transport_records(model, addedRxns, fromComp, toComp)
addedRxns = addedRxns(:)';
names = cell(1, numel(addedRxns));
entries = cell(1, numel(addedRxns));

for k = 1:numel(addedRxns)
    i = find(strcmp(model.rxns, addedRxns{k}), 1);
    names{k} = model.rxnNames{i};
    entries{k} = struct( ...
        'name', model.rxnNames{i}, ...
        'lower_bound', double(model.lb(i)), ...
        'upper_bound', double(model.ub(i)), ...
        'from_species', species_side(model, i, fromComp), ...
        'to_species', species_side(model, i, toComp));
end

[~, order] = sort(names);
records = entries(order);
if isempty(records)
    records = {};
end
end


function out = species_side(model, rxnIdx, compId)
% The (name, coefficient) of the one metabolite this transport has in
% compId --- a transport reaction has exactly one on each side.
compIdx = find(strcmp(model.comps, compId), 1);
metIdx = find(model.S(:, rxnIdx) ~= 0 & model.metComps == compIdx, 1);
if isempty(metIdx)
    error('add_transport_reactions_smallyeast:noSpecies', ...
        'reaction %s has no metabolite in compartment %s', model.rxns{rxnIdx}, compId);
end
% full(): indexing a sparse S yields a sparse scalar, and jsonencode refuses
% one ("Unable to encode sparse objects").
out = struct('name', model.metNames{metIdx}, 'coefficient', double(full(model.S(metIdx, rxnIdx))));
end


function out = as_cellstr(value)
if ischar(value)
    out = {value};
elseif iscell(value)
    out = value(:)';
    for k = 1:numel(out)
        if isstring(out{k})
            out{k} = char(out{k});
        end
    end
else
    out = {};
end
end
