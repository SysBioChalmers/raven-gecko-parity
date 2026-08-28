function results = kcat_chain_ectestgem(ctx)
% MATLAB side of the kcat-chain scenario.
%
% One flowing ecModel, walked through the real pipeline order, mirroring run.py.
% Conventions carried over from the earlier scenarios in this chain: an infinite bound
% is a class and a zero; multi-key records are sorted on keys joined with char(1); an
% error is a flag, not a message.
%
% loadBRENDAdata, applyCustomKcats (with no explicit customKcats struct) and
% getStandardKcat's uniprot load all resolve their fixture through the adapter's own
% params.path, unlike their Python counterparts, which each take an explicit path. A
% *copy* of the adapter --- ModelAdapter is a value class, so this cannot affect the
% original, same pattern as ec_model_io_ectestgem.m --- has its params.path redirected
% to this scenario's own data/ folder for those calls.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

rxnsToAdd.rxns      = {'R2a'; 'R6'};
rxnsToAdd.equations = {'m1[c] <=> m2[c]'; 'm1[c] => m2[c]'};
rxnsToAdd.grRules   = {'G1 and G2 or G3'; ''};
model = addRxns(model, rxnsToAdd, 3);

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcatAdapter = adapter;
kcatAdapter.params.path = ctx.inputs.scenario_root;

results.fuzzy = checkpoint_fuzzy(ecModel, kcatAdapter);
[results.dlkcat, mergedList] = checkpoint_dlkcat(ecModel, results.fuzzy.kcatListFuzzy, adapter, kcatAdapter, ctx.inputs);
results.fuzzy = rmfield(results.fuzzy, 'kcatListFuzzy');
[results.selection, ecModel] = checkpoint_selection(ecModel, mergedList, kcatAdapter);
[results.standard, ecModel] = checkpoint_standard(ecModel, kcatAdapter);
results.constraints = checkpoint_constraints(ecModel, kcatAdapter);

end


% --------------------------------------------------------------------------- %
% fuzzy: loadBRENDAdata + fuzzyKcatMatching
% --------------------------------------------------------------------------- %

function out = checkpoint_fuzzy(ecModel, kcatAdapter)
[KCATcell, ~] = loadBRENDAdata(kcatAdapter);

records = cell(1, numel(KCATcell{1}));
for k = 1:numel(KCATcell{1})
    records{k} = struct('eccode', KCATcell{1}{k}, 'substrate', KCATcell{2}{k}, ...
        'organism', KCATcell{3}{k}, 'kcat', double(KCATcell{4}(k)));
end
keys = cellfun(@(r) [r.eccode char(1) r.substrate char(1) r.organism], records, 'UniformOutput', false);
[~, order] = sort(keys);
out.brenda_kcat_max = records(order);

kcatListFuzzy = fuzzyKcatMatching(ecModel, [], kcatAdapter);
out.matches = match_records(kcatListFuzzy);
out.kcatListFuzzy = kcatListFuzzy;
end


function out = match_records(kcatList)
n = numel(kcatList.rxns);
records = cell(1, n);
for k = 1:n
    ec = '';
    if ~isempty(kcatList.eccodes{k})
        ec = kcatList.eccodes{k};
    end
    origin = -1;
    if ~isnan(kcatList.origin(k))
        origin = double(kcatList.origin(k));
    end
    wc = -1;
    if ~isnan(kcatList.wildcardLvl(k))
        wc = double(kcatList.wildcardLvl(k));
    end
    records{k} = struct('reaction', kcatList.rxns{k}, 'kcat', double(kcatList.kcats(k)), ...
        'eccode', ec, 'origin', origin, 'wildcard_level', wc);
end
[~, order] = sort(kcatList.rxns);
out = records(order);
end


% --------------------------------------------------------------------------- %
% dlkcat: writeDLKcatInput + readDLKcatOutput + mergeDLKcatAndFuzzyKcats
% --------------------------------------------------------------------------- %

function [out, mergedList] = checkpoint_dlkcat(ecModel, kcatListFuzzy, adapter, kcatAdapter, inputs)
ecRxnsMask = ismember(ecModel.ec.rxns, {'R2a_EXP_1', 'R2a_EXP_2'});
written = writeDLKcatInput(ecModel, 'ecRxns', ecRxnsMask, 'modelAdapter', adapter, ...
    'onlyWithSmiles', false, 'filename', inputs.dlkcat_write_target, 'overwrite', true);

n = size(written, 2);
writtenRecords = cell(1, n);
for k = 1:n
    writtenRecords{k} = struct('reaction', written{1,k}, 'gene', written{2,k}, 'substrate', written{3,k});
end
keys = cellfun(@(r) [r.reaction char(1) r.gene], writtenRecords, 'UniformOutput', false);
[~, order] = sort(keys);
out.written_input = writtenRecords(order);

kcatListDLKcat = readDLKcatOutput(ecModel, 'outFile', inputs.dlkcat_output_path, 'modelAdapter', adapter);
m = numel(kcatListDLKcat.rxns);
dlkcatRecords = cell(1, m);
for k = 1:m
    dlkcatRecords{k} = struct('reaction', kcatListDLKcat.rxns{k}, 'gene', kcatListDLKcat.genes{k}, ...
        'kcat', double(kcatListDLKcat.kcats(k)));
end
keys = cellfun(@(r) [r.reaction char(1) r.gene], dlkcatRecords, 'UniformOutput', false);
[~, order] = sort(keys);
out.read_output = dlkcatRecords(order);

mergedList = mergeDLKcatAndFuzzyKcats(kcatListDLKcat, kcatListFuzzy);
p = numel(mergedList.rxns);
mergedRecords = cell(1, p);
for k = 1:p
    mergedRecords{k} = struct('reaction', mergedList.rxns{k}, 'kcat', double(mergedList.kcats(k)), ...
        'source', mergedList.kcatSource{k});
end
keys = cellfun(@(r) [r.reaction char(1) r.source], mergedRecords, 'UniformOutput', false);
[~, order] = sort(keys);
out.merged = mergedRecords(order);
end


% --------------------------------------------------------------------------- %
% selection: selectKcatValue + applyCustomKcats + getKcatAcrossIsozymes
% --------------------------------------------------------------------------- %

function [out, ecModel] = checkpoint_selection(ecModel, mergedList, kcatAdapter)
ecModel = selectKcatValue(ecModel, mergedList, 'criteria', 'max');
out.after_select_max = kcat_rows(ecModel, ecModel.ec.rxns);

% MATLAB's selectKcatValue.m computes [selectedKcats(i),j] = median(...)/mean(...)
% for these two criteria --- a two-output call standard MATLAB median/mean do not
% support (only max/min do). Confirmed by direct execution: this errors
% unconditionally with "Too many output arguments" whenever it reaches a reaction
% needing aggregation, i.e. on any non-empty kcatList. geckopy's apply_kcat_list has
% no such restriction. Asserted here rather than avoided.
try
    selectKcatValue(ecModel, mergedList, 'criteria', 'median');
    out.select_median.raised = false;
catch
    out.select_median.raised = true;
end

ecModel = getKcatAcrossIsozymes(ecModel);
out.after_isozyme_fill = kcat_rows(ecModel, ecModel.ec.rxns);

% customKcats.tsv's only row targets R3 by reaction id alone (mode A: no protein
% listed). MATLAB's applyCustomKcats.m only ever writes ec.kcat in this branch,
% leaving ec.source/ec.notes at whatever they already were (here: 'brenda', from the
% fuzzy match). geckopy's apply_custom_kcats shares one write path across all three
% modes and always sets source='custom' and appends the note. Both sides apply the
% same new kcat; source/notes are the deliberately-asserted difference.
ecModel = applyCustomKcats(ecModel, 'modelAdapter', kcatAdapter);
out.after_custom_kcats = kcat_rows(ecModel, {'R3'});
end


function out = kcat_rows(ecModel, rxnIds)
[~, idx] = ismember(rxnIds, ecModel.ec.rxns);
keep = idx > 0;
rxnIds = rxnIds(keep);
idx = idx(keep);
records = cell(1, numel(idx));
for k = 1:numel(idx)
    i = idx(k);
    % Lowercased: geckopy's apply_kcat_list lowercases MATLAB's raw kcatSource
    % string and appends fuzzy wildcard/origin detail --- a documented
    % MATLAB-COMPAT choice (select_kcat_value.py), not a divergence this
    % scenario is asserting, so the checkpoint compares on the token both
    % sides agree on (see run.py's _source_token, which strips that detail).
    src = '';
    if ~isempty(ecModel.ec.source{i})
        src = lower(ecModel.ec.source{i});
    end
    nt = '';
    if ~isempty(ecModel.ec.notes{i})
        nt = ecModel.ec.notes{i};
    end
    records{k} = struct('reaction', rxnIds{k}, 'kcat', double(ecModel.ec.kcat(i)), ...
        'source', src, 'notes', nt);
end
[~, order] = sort(rxnIds);
out = records(order);
end


% --------------------------------------------------------------------------- %
% standard: getStandardKcat + removeStandardKcat
% --------------------------------------------------------------------------- %

function [out, ecModel] = checkpoint_standard(ecModel, kcatAdapter)
beforeRxns = sort(ecModel.ec.rxns(:));

[ecModel, ~, ~, ~, ~] = getStandardKcat(ecModel, 'modelAdapter', kcatAdapter);
afterRxns = sort(ecModel.ec.rxns(:));
newRxns = setdiff(afterRxns, beforeRxns);

out.new_ec_rxns = reshape(sort(newRxns), 1, []);
out.r6_and_r2a_rev = kcat_rows(ecModel, {'R6', 'R2a_REV_EXP_1', 'R2a_REV_EXP_2'});
out.all_after_assign = kcat_rows(ecModel, afterRxns);

probe = removeStandardKcat(ecModel);
out.after_remove.ec_rxns = reshape(sort(probe.ec.rxns(:)), 1, []);
out.after_remove.rows = kcat_rows(probe, sort(probe.ec.rxns(:)));
end


% --------------------------------------------------------------------------- %
% constraints: applyKcatConstraints
% --------------------------------------------------------------------------- %

function out = checkpoint_constraints(ecModel, kcatAdapter)
ecModel = applyKcatConstraints(ecModel);
out.coefficients = prot_coefficients(ecModel);
out.light_partial_isozyme = light_partial_isozyme_case();
end


function out = prot_coefficients(model)
protIdx = find(startsWith(model.mets, 'prot_'));
records = {};
for p = 1:numel(protIdx)
    row = protIdx(p);
    [~, rxnIdx, vals] = find(model.S(row, :));
    for k = 1:numel(rxnIdx)
        records{end+1} = struct('reaction', model.rxns{rxnIdx(k)}, ...
            'metabolite', model.mets{row}, 'coefficient', full(double(vals(k)))); %#ok<AGROW>
    end
end
keys = cellfun(@(r) [r.reaction char(1) r.metabolite], records, 'UniformOutput', false);
[~, order] = sort(keys);
out = records(order);
end


function out = light_partial_isozyme_case()
% Isolated, purpose-built light-model case: one reaction, two isozymes, only one of
% which has a kcat assigned. MATLAB's applyKcatConstraints.m corrects an unassigned
% isozyme's Inf cost (MW/0) to 0 *before* taking min() across isozymes, so the
% fabricated zero always wins --- silently writing a zero enzyme cost for the whole
% reaction even though the other isozyme has a real, valid kcat. geckopy's
% apply_kcat_constraints skips invalid isozymes before the comparison instead.
% Confirmed by direct execution against a pinned GECKO develop4 worktree; not
% reachable through the shared ecTestGEM fixture, so built standalone here.
clear model
model.rxns = {'R1'};
model.mets = {'prot_pool'};
model.S = sparse(1,1);
model.lb = 0; model.ub = 1000;
model.ec.geckoLight = true;
model.ec.rxns = {'001_R1'; '002_R1'};
model.ec.kcat = [0; 50];
model.ec.mw = [10000; 5000];
model.ec.rxnEnzMat = sparse(2,2);
model.ec.rxnEnzMat(1,1) = 1;
model.ec.rxnEnzMat(2,2) = 1;

model = applyKcatConstraints(model);
out = prot_coefficients(model);
end
