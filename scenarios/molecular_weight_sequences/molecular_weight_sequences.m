function results = molecular_weight_sequences(ctx)
% MATLAB side of the molecular-weight scenario.
%
% One record per sequence, in declaration order --- not sorted, for the same reason
% gpr_dnf_rules.m leaves its rule list in declaration order: this fixture is a flat list of
% independent, hand-chosen test cases rather than model output, and keeping input order is
% what makes a result that stops matching scenario.yml's per-sequence comments easy to
% locate.
%
% calculateMW takes a bare string and returns a double --- no model, no adapter, nothing
% else to resolve on this side either.

sequences = as_cellstr(ctx.inputs.sequences);

records = cell(1, numel(sequences));
for k = 1:numel(sequences)
    records{k} = struct('sequence', sequences{k}, 'mw', double(calculateMW(sequences{k})));
end

% Cell array of structs, not a struct array: jsonencode turns a 1x1 struct array into a
% bare object instead of a one-element array.
results.sequences = records;

end


function out = as_cellstr(value)
% jsondecode returns a cell array of char for a JSON array of strings, but a bare char for
% a single string --- and an empty array for an empty list. Copied from gpr_dnf_rules.m,
% which established this exact idiom for the same jsondecode quirk.
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
