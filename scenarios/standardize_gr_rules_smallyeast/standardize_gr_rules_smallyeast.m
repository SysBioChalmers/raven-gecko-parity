function results = standardize_gr_rules_smallyeast(ctx)
% MATLAB side of the non-DNF GPR detection scenario.
%
% Only indexes2check (via findPotentialErrors' isDnfGrRule check, already
% cross-validated by gpr_dnf_rules) has a Python counterpart. The
% rewritten grRules string and rxnGeneMat outputs do not: cobra
% auto-normalises a GPR's brackets and operator case at assignment time,
% so raven_toolbox has nothing that corresponds to standardizeGrRules'
% own string-rewriting half. See run.py and scenario.yml.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

rewritten = inputs.non_dnf_rule;
model = changeGrRules(model, {char(rewritten.reaction)}, {char(rewritten.grRule)}, ...
    'replace', true);

[~, ~, indexes2check] = standardizeGrRules(model);

results.flagged_reactions = sort_cellstr(model.rxns(indexes2check));

end


function out = sort_cellstr(values)
if isempty(values)
    out = {};
    return
end
out = reshape(sort(values(:)), 1, []);
end
