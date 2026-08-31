function results = save_delta_g_csv_smallyeast(ctx)
% MATLAB side of the deltaG CSV writer scenario.
%
% saveDeltaGCSV and save_delta_g_csv both write one row per entity, in
% model order, verbatim from whatever the model already holds --- neither
% interprets or filters a value on the way out. See run.py and
% scenario.yml.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

model.metDeltaG = nan(numel(model.mets), 1);
model = stamp_field(model, 'metDeltaG', model.mets, inputs.met_values);
model.rxnDeltaG = nan(numel(model.rxns), 1);
model = stamp_field(model, 'rxnDeltaG', model.rxns, inputs.rxn_values);

metPath = [tempname() '.csv'];
rxnPath = [tempname() '.csv'];
cleanupMet = onCleanup(@() delete_if_exists(metPath)); %#ok<NASGU>
cleanupRxn = onCleanup(@() delete_if_exists(rxnPath)); %#ok<NASGU>

saveDeltaGCSV(model, 'metCsv', metPath, 'rxnCsv', rxnPath);

metTable = readtable(metPath);
rxnTable = readtable(rxnPath);

results.met_row_count = height(metTable);
results.rxn_row_count = height(rxnTable);

metIds = as_cellstr(inputs.met_ids);
metRecords = cell(1, numel(metIds));
for k = 1:numel(metIds)
    metRecords{k} = read_row(metTable, metIds{k});
end
results.metabolites = metRecords;

rxnIds = as_cellstr(inputs.rxn_ids);
rxnRecords = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    rxnRecords{k} = read_row(rxnTable, rxnIds{k});
end
results.reactions = rxnRecords;

end


function model = stamp_field(model, fieldname, ids, values)
% jsondecode gives a scalar struct for a JSON object, so fields() and
% direct indexing is how the declared id -> value mapping is recovered.
valueFields = fieldnames(values);
for k = 1:numel(valueFields)
    idx = find(strcmp(ids, valueFields{k}), 1);
    model.(fieldname)(idx) = values.(valueFields{k});
end
end


function out = read_row(T, entityId)
idCol = T.Var1;
if ~iscell(idCol)
    idCol = cellstr(idCol);
end
idx = find(strcmp(idCol, entityId), 1);
out = struct('entity', entityId, 'value', json_safe(T.Var2(idx)));
end


function out = json_safe(value)
% jsonencode turns a raw NaN into JSON null on the MATLAB side, where the
% harness's own Python-side canonicalisation turns a NaN float into the
% string "NaN" instead --- collect_matlab reads MATLAB's own jsonencode
% output verbatim, with no equivalent canonicalisation step applied to
% it. Matched here by hand so "no value" compares equal instead of
% comparing null against "NaN" as if they were different answers.
if isnan(value)
    out = 'NaN';
else
    out = value;
end
end


function delete_if_exists(path)
if isfile(path)
    delete(path);
end
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
