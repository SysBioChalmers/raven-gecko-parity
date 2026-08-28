function parity_run(scenarioDir, contextFile, outputFile)
% parity_run  Run the MATLAB side of a parity scenario and write its results as JSON.
%
% Every scenario directory holds a function file named after the scenario id, e.g.
% scenarios/elemental_balance_smallyeast/elemental_balance_smallyeast.m, taking a context
% struct and returning a results struct. This harness loads the context, calls that
% function, and writes a result document in the same shape the Python side produces, so
% `parity compare` can diff the two.
%
% Usage
% -----
%   parity_run(scenarioDir)
%       Uses <scenarioDir>/.context.json and writes <scenarioDir>/.matlab_result.json.
%       Generate the context first with:  parity run <id> --impl python  (it writes one),
%       or by hand --- it is a small JSON file.
%
%   parity_run(scenarioDir, contextFile, outputFile)
%       Explicit paths. This is the form `parity run --impl matlab` invokes.
%
% Both RAVEN (or GECKO) and this repo's matlab/ directory must be on the MATLAB path.

if nargin < 1 || isempty(scenarioDir)
    error('parity_run:noScenario', 'a scenario directory is required');
end
if nargin < 2 || isempty(contextFile)
    contextFile = fullfile(scenarioDir, '.context.json');
end
if nargin < 3 || isempty(outputFile)
    outputFile = fullfile(scenarioDir, '.matlab_result.json');
end

if ~isfile(contextFile)
    error('parity_run:noContext', ...
        ['no context file at %s --- generate one by running the Python side first ' ...
         '(parity run <id> --impl python), or write it by hand'], contextFile);
end

ctx = jsondecode(fileread(contextFile));

[~, scenarioId] = fileparts(strip_trailing_sep(scenarioDir));
entryFile = fullfile(scenarioDir, [scenarioId '.m']);
if ~isfile(entryFile)
    error('parity_run:noEntry', 'scenario %s has no %s.m', scenarioId, scenarioId);
end

% Put the scenario directory on the path only for the duration of the run, so two
% scenarios can never shadow each other.
previousPath = path();
cleanup = onCleanup(@() path(previousPath));
addpath(scenarioDir);

entry = str2func(scenarioId);
results = entry(ctx);

document = struct( ...
    'result_version', 1, ...
    'scenario', scenarioId, ...
    'implementation', 'matlab', ...
    'runtime', ['matlab ' version('-release')], ...
    'results', canonicalize_for_json(results));

fid = fopen(outputFile, 'w');
if fid < 0
    error('parity_run:cannotWrite', 'cannot write %s', outputFile);
end
closeFile = onCleanup(@() fclose(fid));
fwrite(fid, jsonencode(document, 'PrettyPrint', true), 'char');

fprintf('%s [matlab] -> %s\n', scenarioId, outputFile);

end


function p = strip_trailing_sep(p)
% fileparts on a path ending in a separator returns an empty name, which would lose the
% scenario id.
while ~isempty(p) && (endsWith(p, '/') || endsWith(p, '\'))
    p = p(1:end-1);
end
end


function out = canonicalize_for_json(value)
% canonicalize_for_json  Make a results value safe for jsonencode, mirroring
% src/parity/scenarios.py's _canonical(): a NaN scalar becomes the char row
% 'NaN', +Inf becomes 'Infinity', -Inf becomes '-Infinity'. Everything else is
% walked recursively (struct fields, cell array elements, struct array
% elements, numeric array elements) and otherwise left untouched.
%
% Without this, jsonencode turns a raw NaN/Inf into JSON null, where the
% Python side's own canonicalisation turns the same "no value" into a
% descriptive string instead --- a MATLAB scenario result and the equivalent
% Python one would then disagree in `parity compare` even when the
% underlying values genuinely agree. See scenarios/delta_g_csv_smallyeast,
% which hit this directly and worked around it locally before this function
% existed.

if isstruct(value)
    out = value;
    fields = fieldnames(value);
    for k = 1:numel(value)
        for i = 1:numel(fields)
            out(k).(fields{i}) = canonicalize_for_json(value(k).(fields{i}));
        end
    end
elseif iscell(value)
    out = cell(size(value));
    for k = 1:numel(value)
        out{k} = canonicalize_for_json(value{k});
    end
elseif isnumeric(value)
    if issparse(value)
        value = full(value);
    end
    if isscalar(value)
        out = canonicalize_scalar(value);
    else
        % A numeric array: canonicalize element by element via a cell
        % array, so a mix of ordinary numbers and NaN/Inf sentinel strings
        % can coexist in the same JSON array --- a plain numeric array
        % cannot hold a string next to a number. jsonencode renders a cell
        % array of scalars as the same JSON array a plain numeric array
        % would, so this changes nothing when no element needs it.
        out = cell(size(value));
        for k = 1:numel(value)
            out{k} = canonicalize_scalar(value(k));
        end
    end
else
    % char, string, logical, empty --- left alone.
    out = value;
end
end


function out = canonicalize_scalar(value)
if isnan(value)
    out = 'NaN';
elseif isinf(value)
    if value > 0
        out = 'Infinity';
    else
        out = '-Infinity';
    end
else
    out = value;
end
end
