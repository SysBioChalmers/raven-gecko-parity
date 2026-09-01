function results = enzyme_usage_ectestgem(ctx)
% MATLAB side of the enzyme-usage scenario.
%
% A single solved ecModel, walked through the three post-solve reporting functions in
% sequence: getEnzymeUsage's per-protein usage/capacity readout, reportEnzymeUsage's two
% summary tables, and getConcControlCoeffs's growth-sensitivity coefficients. Mirrors
% run.py; see scenario.yml for why R2 and R4 are both blocked (a real LP degeneracy in
% this fixture with either one left open, not a bug on either side) and what
% getConcControlCoeffs's fixture does, and does not, exercise of that function's own
% documented MATLAB-vs-geckopy algorithmic difference.

% The solver is named by the scenario rather than inherited, so that both sides are
% demonstrably solving with the same one. The preference is global and the nightly runs
% several scenarios in one MATLAB session, so whatever was set is put back on the way out.
previousSolver = getpref('RAVEN', 'solver', '');
restoreSolver = onCleanup(@() restore_solver(previousSolver));
setRavenSolver(char(ctx.inputs.matlab_solver));

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

blocked = ctx.inputs.blocked_reactions;
for i = 1:numel(blocked)
    idx = strcmp(model.rxns, blocked{i});
    model.lb(idx) = 0;
    model.ub(idx) = 0;
end

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcats = ctx.inputs.kcats;
kcatRxns = fieldnames(kcats);
for i = 1:numel(kcatRxns)
    idx = strcmp(ecModel.ec.rxns, kcatRxns{i});
    ecModel.ec.kcat(idx) = kcats.(kcatRxns{i});
    ecModel.ec.source(idx) = {'manual'};
end

protData = loadProtData(1, [], [], adapter);
ecModel = fillEnzConcs(ecModel, protData);
ecModel = constrainEnzConcs(ecModel);

ecModel = applyKcatConstraints(ecModel);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);

sol = solveLP(ecModel);

usageData = getEnzymeUsage(ecModel, sol.x);
results.usage.objective = double(sol.f);
results.usage.proteins = usage_rows(usageData);

report = reportEnzymeUsage(ecModel, usageData, ...
    'highCapUsage', double(ctx.inputs.high_cap_usage), ...
    'topAbsUsage', double(ctx.inputs.top_abs_usage));
results.report.high_cap_usage = report_table_rows(report.highCapUsage, 'capUsage', 'cap_usage');
% Confirmed divergence, asserted rather than avoided: reportEnzymeUsage.m always
% returns exactly topAbsUsage rows -- an enzyme with no flux-carrying reaction still
% gets a placeholder row (isscalar(find(carriedFlux)) is false for zero matches, the
% same branch a genuinely multi-reaction enzyme takes). report_enzyme_usage instead
% skips any enzyme with no flux-carrying reaction outright, so it can return fewer
% rows. See scenario.yml and raven-gecko-parity#18 for the mechanism on each side.
results.report.top_abs_usage = report_table_rows(report.topAbsUsage, 'percUsage', 'perc_usage');
results.report.total_usage_flux = double(report.totalUsageFlux);

[enz, controlCoeffs] = getConcControlCoeffs(ecModel);
results.control_coeffs = control_coeff_rows(ecModel.ec.enzymes, enz, controlCoeffs);

end


function out = usage_rows(usageData)
n = numel(usageData.protID);
records = cell(1, n);
for k = 1:n
    records{k} = struct('protein', usageData.protID{k}, 'ub', double(usageData.UB(k)), ...
        'abs_usage', double(usageData.absUsage(k)), 'cap_usage', double(usageData.capUsage(k)));
end
[~, order] = sort(usageData.protID);
out = records(order);
end


function out = report_table_rows(tbl, srcCol, dstField)
n = height(tbl);
records = cell(1, n);
for k = 1:n
    records{k} = struct('protein', tbl.protID{k}, 'abs_usage', double(tbl.absUsage(k)));
    records{k}.(dstField) = double(tbl.(srcCol)(k));
end
[~, order] = sort(tbl.protID);
out = records(order);
end


function out = control_coeff_rows(enzymes, enz, controlCoeffs)
n = numel(enzymes);
records = cell(1, n);
for k = 1:n
    records{k} = struct('protein', enzymes{k}, 'analysed', logical(enz(k)), 'coeff', double(controlCoeffs(k)));
end
[~, order] = sort(enzymes);
out = records(order);
end


function restore_solver(previous)
if ~isempty(previous)
    setRavenSolver(previous);
end
end
