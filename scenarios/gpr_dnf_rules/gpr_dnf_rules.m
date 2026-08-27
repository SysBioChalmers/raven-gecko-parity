function results = gpr_dnf_rules(ctx)
% MATLAB side of the GPR normalisation scenario.
%
% Same shape as run.py: one record per rule, in the order scenario.yml lists
% them, with the clauses left in the order the parser produced them. Nothing is
% sorted here --- clause order and gene-within-clause order are documented
% behaviour on both sides, so sorting would hide a real disagreement.
%
% The chain compared is parseGrRule -> grRuleToDNF, which is what a caller
% travels; grRuleToDNF does the parse itself when handed a string.

rules = as_cellstr(ctx.inputs.rules);

analysed = cell(1, numel(rules));
for k = 1:numel(rules)
    analysed{k} = analyse(rules{k});
end

results.n_rules = numel(analysed);
results.n_unparsable = count_flag(analysed, 'parsed', false);
results.n_dnf = count_flag(analysed, 'is_dnf', true);

% Cell array of structs, not a struct array: jsonencode turns a 1x1 struct
% array into a bare object instead of a one-element array.
results.rules = analysed;

end


function record = analyse(rule)
% RAVEN signals a malformed rule by raising RAVEN:badGrRule. cobra signals it
% by warning and yielding an empty GPR, so `parsed` is each implementation's
% own verdict rather than a shared definition --- which is the point: a rule
% one side rejects and the other silently empties is a difference worth seeing.
try
    tree = parseGrRule(rule);
    clauses = grRuleToDNF(tree);
    tf = isDnfGrRule(tree);
catch ME
    if ~strcmp(ME.identifier, 'RAVEN:badGrRule')
        rethrow(ME)
    end
    % Every key always present, so an unparsable rule reads as a value
    % difference rather than a structural one.
    record = struct('rule', rule, 'parsed', false, 'is_dnf', false, ...
        'n_clauses', 0, 'clauses', {{}});
    return
end

% Row orientation throughout: jsonencode writes a cell array as a JSON array,
% and keeping the shape explicit keeps a 1-element clause an array too.
clauses = clauses(:)';
for i = 1:numel(clauses)
    clauses{i} = clauses{i}(:)';
end

record = struct('rule', rule, 'parsed', true, 'is_dnf', logical(tf), ...
    'n_clauses', numel(clauses), 'clauses', {clauses});
end


function n = count_flag(records, field, wanted)
n = 0;
for k = 1:numel(records)
    if records{k}.(field) == wanted
        n = n + 1;
    end
end
end


function out = as_cellstr(value)
% jsondecode returns a cell array of char for a JSON array of strings, but a
% bare char for a single string --- and an empty array for an empty list.
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
