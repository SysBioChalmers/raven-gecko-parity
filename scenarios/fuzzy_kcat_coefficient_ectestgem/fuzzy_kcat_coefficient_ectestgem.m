function results = fuzzy_kcat_coefficient_ectestgem(ctx)
% MATLAB side of the fuzzy-kcat coefficient scenario, mirroring run.py.
%
% R7 (2 m1 + 0.5 m2 => e1, EC 1.1.2.1) has a BRENDA row on m1 only, so its kcat is 40
% when divided by m1's coefficient and 160 when divided by the smallest coefficient.
% loadBRENDAdata resolves its files through the adapter's params.path, so a copy of the
% adapter (a value class) is pointed at this scenario's data/ folder.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

rxnsToAdd.rxns      = {'R7'};
rxnsToAdd.equations = {'2 m1[c] + 0.5 m2[c] => e1[e]'};
rxnsToAdd.grRules   = {'G1'};
rxnsToAdd.eccodes   = {'1.1.2.1'};
model = addRxns(model, rxnsToAdd, 3);

ecModel = makeEcModel(model, false, adapter);
ecModel = getECfromGEM(ecModel);

kcatAdapter = adapter;
kcatAdapter.params.path = ctx.inputs.scenario_root;

kcatListFuzzy = fuzzyKcatMatching(ecModel, [], kcatAdapter);
results.matches = match_records(kcatListFuzzy);
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
