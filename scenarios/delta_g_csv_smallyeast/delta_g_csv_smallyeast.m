function results = delta_g_csv_smallyeast(ctx)
% MATLAB side of the deltaG CSV loader scenario.
%
% loadDeltaGCSV and load_delta_g_csv agree on both the ordinary case ---
% match by id, leave anything the CSV doesn't mention untouched --- and,
% by their current defaults, on yeast-GEM's own "no measurement" sentinel
% value (10000000.0): both store every matched CSV value exactly as
% written, including the sentinel, rather than treating it as absent.
% See run.py and scenario.yml.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

model = loadDeltaGCSV(model, 'metCsv', char(inputs.met_csv), 'rxnCsv', char(inputs.rxn_csv));

metIds = as_cellstr(inputs.met_ids);
metRecords = cell(1, numel(metIds));
for k = 1:numel(metIds)
    i = find(strcmp(model.mets, metIds{k}), 1);
    metRecords{k} = struct('entity', metIds{k}, 'value', json_safe(model.metDeltaG(i)));
end
results.metabolites = metRecords;

rxnIds = as_cellstr(inputs.rxn_ids);
rxnRecords = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    i = find(strcmp(model.rxns, rxnIds{k}), 1);
    rxnRecords{k} = struct('entity', rxnIds{k}, 'value', json_safe(model.rxnDeltaG(i)));
end
results.reactions = rxnRecords;

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
