function results = delta_g_csv_smallyeast(ctx)
% MATLAB side of the deltaG CSV load/save scenario.
%
% loadDeltaGCSV/saveDeltaGCSV and load_delta_g_csv/save_delta_g_csv agree
% on the ordinary case --- match by id, leave anything the CSV doesn't
% mention untouched --- and, since raven-gecko-parity#67/#16, on
% yeast-GEM's own "no measurement" placeholder value too: neither side
% interprets a CSV value at all any more. See run.py and scenario.yml.

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

% Both writes go to a temporary directory, not into the repository: the
% point is what the writer produces, not an artefact anyone needs to keep.
workdir = tempname;
mkdir(workdir);
cleanup = onCleanup(@() rmdir(workdir, 's'));
outMetCsv = fullfile(workdir, 'met_out.csv');
outRxnCsv = fullfile(workdir, 'rxn_out.csv');
saveDeltaGCSV(model, 'metCsv', outMetCsv, 'rxnCsv', outRxnCsv);
results.saved_metabolites = read_csv_rows(outMetCsv);
results.saved_reactions = read_csv_rows(outRxnCsv);

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


function records = read_csv_rows(path)
% The full contents of a saved CSV, sorted by id --- what was actually
% written, not what a later load of it would read back.
G = readtable(path);
ids = G.(G.Properties.VariableNames{1});
values = G.(G.Properties.VariableNames{2});
[~, order] = sort(ids);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct('entity', ids{i}, 'value', json_safe(values(i)));
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
