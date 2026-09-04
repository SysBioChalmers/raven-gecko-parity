function results = export_to_excel_smallyeast(ctx)
% MATLAB side of the Excel export scenario.
%
% exportToExcelFormat hides a reaction's LOWER BOUND / UPPER BOUND cell
% when it equals the model's own declared default
% (model.annotation.defaultLB/defaultUB --- smallYeast declares
% -1000/1000), and hides an irreversible reaction's lower bound
% separately whenever it is exactly 0, regardless of the declared
% default. export_to_excel matches this exactly (see run.py and
% scenario.yml). Both sides are expected to agree here.
%
% Neither side provides a reader for its own export ("Excel import is
% intentionally excluded", by both docstrings), so this reads the
% freshly written file back with readcell purely as test scaffolding.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

outPath = [tempname() '.xlsx'];
cleanupFile = onCleanup(@() delete_if_exists(outPath)); %#ok<NASGU>
exportToExcelFormat(model, 'fileName', outPath);

C = readcell(outPath, 'Sheet', 'RXNS');
headers = C(1, :);
idCol = find(strcmp(headers, 'ID'), 1);
lbCol = find(strcmp(headers, 'LOWER BOUND'), 1);
ubCol = find(strcmp(headers, 'UPPER BOUND'), 1);
idColumn = C(2:end, idCol);

reactionIds = as_cellstr(inputs.reaction_ids);
records = cell(1, numel(reactionIds));
for k = 1:numel(reactionIds)
    rowIdx = find(strcmp(idColumn, reactionIds{k}), 1) + 1;
    records{k} = struct( ...
        'reaction', reactionIds{k}, ...
        'lower_bound', cell_to_value(C{rowIdx, lbCol}), ...
        'upper_bound', cell_to_value(C{rowIdx, ubCol}));
end
results.rxns_bounds = records;

end


function out = cell_to_value(rawCell)
% A hidden bound comes back from readcell as missing (an empty cell) or
% as an empty char. parity_run.m's canonicalize_for_json reserves NaN for
% a genuinely missing NUMERIC value (which it turns into the string
% "NaN", matching the Python side's own _canonical()) --- a hidden RXNS
% bound cell is a different thing, a deliberate absence, the same as
% Python's None, so it must come back as MATLAB's own `missing` (left
% untouched by canonicalize_for_json, and jsonencode's it to JSON null)
% rather than NaN, or it would wrongly collide with the NaN convention.
if (isa(rawCell, 'missing')) || (ischar(rawCell) && isempty(rawCell))
    out = missing;
else
    out = rawCell;
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
