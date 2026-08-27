function results = protein_pool_ectestgem(ctx)
% MATLAB side of the protein-pool scenario.
%
% Must return exactly the shape run.py returns --- same field names, same ordering rules,
% same conventions --- because `parity compare` diffs the two structurally. Three
% conventions carried over from the earlier scenarios in this chain, all for the same
% reason: a divergence in the harness must not read as a divergence in GECKO.
%
%   * concentrations --- a NaN entry (no measurement) is emitted as a flag and a zero,
%     because jsonencode writes NaN as null, which the Python side would read back as the
%     string "NaN" rather than the same absence;
%   * sorting --- concentration and bound lists are sorted by enzyme id, because the point
%     of those two checkpoints is whether the right value landed on the right enzyme, not
%     whether expansion order was preserved (that question belongs to
%     ec_model_expansion_ectestgem, and is answered there);
%   * an error is a flag, not a message --- light_constrain_raises records whether
%     constrainEnzConcs refused, not what it said, since the two languages phrase an error
%     differently and comparing that text would be a false difference on its own.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

override = ctx.inputs.pool_size_override;

poolSize = struct();
poolSize.full  = pool_size_checkpoint(model, false, adapter, override);
poolSize.light = pool_size_checkpoint(model, true,  adapter, override);
results.pool_size = poolSize;

protData = loadProtData(1, [], [], adapter);
results.prot_data.uniprot_ids = reshape(protData.uniprotIDs, 1, []);
results.prot_data.abundances  = reshape(double(protData.abundances(:, 1)), 1, []);

% Name-value form, not positional: calculateFfactor always loads the UniProt database
% (used only inside its paxDB.tsv branch, but fetched unconditionally), so modelAdapter is
% required even though protData is supplied directly and enzymes is left at its default.
ecForF = makeEcModel(model, false, adapter);
results.f_factor = struct( ...
    'default', double(calculateFfactor(ecForF, 'protData', protData, 'modelAdapter', adapter)), ...
    'subset',  double(calculateFfactor(ecForF, 'protData', protData, ...
        'enzymes', cellstr(ctx.inputs.f_factor_enzymes), 'modelAdapter', adapter)));

ecFull = makeEcModel(model, false, adapter);
ecFull = fillEnzConcs(ecFull, protData);
concsFull = concs(ecFull);
ecFull = constrainEnzConcs(ecFull);
constrainedFull = usage_bounds(ecFull);

partialIds = cellstr(ctx.inputs.partial_proteins);
keep = ismember(protData.uniprotIDs, partialIds);
partialData.uniprotIDs = protData.uniprotIDs(keep);
partialData.abundances = protData.abundances(keep, :);

ecPartial = makeEcModel(model, false, adapter);
ecPartial = fillEnzConcs(ecPartial, partialData);
concsPartial = concs(ecPartial);
ecPartial = constrainEnzConcs(ecPartial);
constrainedPartial = usage_bounds(ecPartial);
ecPartial = constrainEnzConcs(ecPartial, 'removeConstraints', true);
removedPartial = usage_bounds(ecPartial);
concsAfterRemove = concs(ecPartial);

% Dot-assignment throughout, not struct('field', {cellValue}, ...): the latter needs every
% cell-valued argument wrapped in an extra {} to stop struct() distributing it across a
% struct array, which is easy to get wrong with several cell-array fields in one call.
results.enzyme_concs.full.concs = concsFull;
results.enzyme_concs.full.constrained = constrainedFull;

results.enzyme_concs.partial.concs = concsPartial;
results.enzyme_concs.partial.constrained = constrainedPartial;
results.enzyme_concs.partial.concs_survive_removal = isequal(concsAfterRemove, concsPartial);
results.enzyme_concs.partial.removed = removedPartial;

ecLight = makeEcModel(model, true, adapter);
ecLight = fillEnzConcs(ecLight, protData);
try
    constrainEnzConcs(ecLight);
    results.light_constrain_raises = false;
catch
    results.light_constrain_raises = true;
end

end


function out = pool_size_checkpoint(model, geckoLight, adapter, override)
ecModel = makeEcModel(model, geckoLight, adapter);
ecModel = setProtPoolSize(ecModel, [], [], [], adapter);
defaultBound = ecModel.ub(strcmp(ecModel.rxns, 'prot_pool_exchange'));
ecModel = setProtPoolSize(ecModel, override.p_tot, override.f, override.sigma);
overrideBound = ecModel.ub(strcmp(ecModel.rxns, 'prot_pool_exchange'));
out = struct('default', double(defaultBound), 'override', double(overrideBound));
end


function out = concs(model)
% ec.concs paired with the enzyme it belongs to, sorted by enzyme id --- see the module
% docstring for why sorted here where ec_model_expansion_ectestgem leaves ec.enzymes itself
% unsorted.
[enzymeIds, order] = sort(model.ec.enzymes(:));
values = double(model.ec.concs(:));
values = values(order);

out = cell(1, numel(enzymeIds));
for k = 1:numel(enzymeIds)
    hasConc = ~isnan(values(k));
    if hasConc
        conc = values(k);
    else
        conc = 0;
    end
    out{k} = struct('enzyme', enzymeIds{k}, 'has_conc', hasConc, 'conc', conc);
end
end


function out = usage_bounds(model)
% usage_prot_<enzyme> upper bounds, sorted by enzyme id.
[enzymeIds, order] = sort(model.ec.enzymes(:));
usageRxns = strcat('usage_prot_', enzymeIds);
[~, idx] = ismember(usageRxns, model.rxns);

out = cell(1, numel(enzymeIds));
for k = 1:numel(enzymeIds)
    out{k} = struct('enzyme', enzymeIds{k}, 'upper_bound', double(model.ub(idx(k))));
end
end
