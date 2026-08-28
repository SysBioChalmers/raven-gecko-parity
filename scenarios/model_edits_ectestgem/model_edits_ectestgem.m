function results = model_edits_ectestgem(ctx)
% MATLAB side of the model-edits scenario.
%
% Five checkpoints, one per entry, each applied to its own fresh copy of a full ecModel
% --- never to the same mutated model twice, so no checkpoint depends on the order the
% others ran in. Conventions carried over from the earlier scenarios in this chain, for the
% same reasons: an infinite bound is a class and a zero; multi-key records are sorted on
% keys joined with char(1); an error is a flag, not a message.

adapter = ModelAdapterManager.getAdapter(ctx.inputs.adapter_matlab);
model = loadConventionalGEM('modelAdapter', adapter);

results.reactions_from_enzyme = checkpoint_reactions_from_enzyme(model, adapter, ctx.inputs);
results.set_kcat              = checkpoint_set_kcat(model, adapter, ctx.inputs);
results.copy_ec               = checkpoint_copy_ec(model, adapter, ctx.inputs);
results.map_rxns              = checkpoint_map_rxns(model, adapter);
results.add_new_rxns          = checkpoint_add_new_rxns(model, adapter, ctx.inputs);

end


function ecModel = fresh(model, adapter)
ecModel = makeEcModel(model, false, adapter);
end


% --------------------------------------------------------------------------- %
% getReactionsFromEnzyme
% --------------------------------------------------------------------------- %

function out = checkpoint_reactions_from_enzyme(model, adapter, inputs)
ecModel = fresh(model, adapter);
out.known        = reactions_from_enzyme_case(ecModel, inputs.known_enzyme);
out.case_variant = reactions_from_enzyme_case(ecModel, inputs.case_variant_enzyme);
out.unknown      = reactions_from_enzyme_case(ecModel, inputs.unknown_enzyme);
end


function out = reactions_from_enzyme_case(ecModel, proteinId)
% getReactionsFromEnzyme never errors --- an unknown protein id yields empty outputs, not
% an exception --- so `raised` is always false here. The field still exists so the shape
% matches geckopy's side, which does raise for the same input.
[rxns, kcat] = getReactionsFromEnzyme(ecModel, proteinId);
[rxns, order] = sort(rxns(:));
kcat = double(kcat(:));
kcat = kcat(order);
out.raised = false;
out.rxns = reshape(rxns, 1, []);
out.kcat = reshape(kcat, 1, []);
end


% --------------------------------------------------------------------------- %
% setKcatForReactions
% --------------------------------------------------------------------------- %

function out = checkpoint_set_kcat(model, adapter, inputs)
suffixed = fresh(model, adapter);
suffixed = setKcatForReactions(suffixed, inputs.kcat_suffixed.rxn, inputs.kcat_suffixed.value);
out.suffixed = kcat_and_source(suffixed, {'R2_EXP_1', 'R2_EXP_2'});

baseScalar = fresh(model, adapter);
baseScalar = setKcatForReactions(baseScalar, inputs.kcat_base_scalar.rxn, inputs.kcat_base_scalar.value);
out.base_scalar = kcat_and_source(baseScalar, {'R2_EXP_1', 'R2_EXP_2'});

% MATLAB accepts a per-isozyme kcat list for an unsuffixed base name, relying on ec.rxns
% order --- geckopy refuses this and asks for the suffixed ids explicitly. Both sides are
% therefore expected to disagree here: `raised` stays false on this side.
baseList = fresh(model, adapter);
baseList = setKcatForReactions(baseList, inputs.kcat_base_list.rxn, inputs.kcat_base_list.values);
out.base_list.raised = false;
listResult = kcat_and_source(baseList, {'R2_EXP_1', 'R2_EXP_2'});
out.base_list.records = listResult.records;
end


function out = kcat_and_source(ecModel, rxnIds)
[~, idx] = ismember(rxnIds, ecModel.ec.rxns);
[rxnIds, order] = sort(rxnIds(:));
idx = idx(order);

records = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    records{k} = struct( ...
        'reaction', rxnIds{k}, ...
        'kcat',     double(ecModel.ec.kcat(idx(k))), ...
        'source',   ecModel.ec.source{idx(k)});
end
out.records = records;
end


% --------------------------------------------------------------------------- %
% copyECtoGEM
% --------------------------------------------------------------------------- %

function out = checkpoint_copy_ec(model, adapter, inputs)
target = inputs.overwrite_target_rxn;

fillEmpty = fresh(model, adapter);
fillEmpty = copyECtoGEM(fillEmpty, false);
out.fill_empty = eccodes_by_reaction(fillEmpty);

overwriteNonempty = fresh(model, adapter);
overwriteNonempty = copyECtoGEM(overwriteNonempty, false);
before = eccode_tokens(overwriteNonempty, target);
overwriteNonempty = copyECtoGEM(overwriteNonempty, false); % idempotent: no new info, no change expected
out.overwrite_false_unchanged = isequal(before, eccode_tokens(overwriteNonempty, target));

% Blank the ec.eccodes entry for `target` before copying, so overwrite=true is asked to
% replace a real annotation with nothing --- the case MATLAB clobbers and geckopy does not.
overwriteEmpty = fresh(model, adapter);
ecIdx = find(strcmp(overwriteEmpty.ec.rxns, target), 1);
if ~isempty(ecIdx)
    overwriteEmpty.ec.eccodes{ecIdx} = '';
end
overwriteEmpty = copyECtoGEM(overwriteEmpty, true);
out.overwrite_true_with_empty = eccode_tokens(overwriteEmpty, target);
end


function out = eccode_tokens(model, rxnId)
% The eccode on one reaction, as a sorted list of tokens --- see run.py for why tokens
% rather than MATLAB's raw string or geckopy's list: the question is which codes land on
% which reaction, not which container holds them.
rxnIdx = find(strcmp(model.rxns, rxnId), 1);
if isempty(rxnIdx) || ~isfield(model, 'eccodes') || isempty(model.eccodes{rxnIdx})
    out = {};
    return
end
tokens = strsplit(model.eccodes{rxnIdx}, ';');
tokens = tokens(~cellfun(@isempty, tokens));
out = sort(tokens);
end


function out = eccodes_by_reaction(model)
% A struct keyed by reaction id, matching geckopy's {rxn_id: tokens} dict: jsonencode
% turns either into the same kind of JSON object. Every fixture reaction id here is
% already a valid MATLAB field name (no leading digit, no punctuation but underscore).
rxnIds = sort(model.rxns(:));
out = struct();
for k = 1:numel(rxnIds)
    out.(rxnIds{k}) = eccode_tokens(model, rxnIds{k});
end
end


% --------------------------------------------------------------------------- %
% mapRxnsToConv
% --------------------------------------------------------------------------- %

function out = checkpoint_map_rxns(model, adapter)
ecModel = fresh(model, adapter);

% One synthetic value per ecModel reaction: the alphabetical rank among this model's own
% reaction ids. A pure function of the id strings, so it does not depend on this
% implementation and geckopy agreeing on row order --- only on agreeing on the *set* of
% ids, already confirmed by ec_model_expansion_ectestgem.
[sortedIds, ~] = sort(ecModel.rxns(:));
rank = containers.Map(sortedIds, num2cell(1:numel(sortedIds)));

fluxVect = zeros(numel(ecModel.rxns), 1);
for k = 1:numel(ecModel.rxns)
    fluxVect(k) = rank(ecModel.rxns{k});
end

[mappedFlux, enzUsageFlux, usageEnz] = mapRxnsToConv(ecModel, model, fluxVect);

[convIds, order] = sort(model.rxns(:));
mappedFlux = mappedFlux(order);
mapped = cell(1, numel(convIds));
for k = 1:numel(convIds)
    mapped{k} = struct('reaction', convIds{k}, 'flux', double(mappedFlux(k)));
end
out.mapped = mapped;

[usageIds, order] = sort(usageEnz(:));
enzUsageFlux = enzUsageFlux(order);
usage = cell(1, numel(usageIds));
for k = 1:numel(usageIds)
    usage{k} = struct('enzyme', usageIds{k}, 'flux', double(enzUsageFlux(k)));
end
out.usage = usage;
end


% --------------------------------------------------------------------------- %
% addNewRxnsToEC
% --------------------------------------------------------------------------- %

function out = checkpoint_add_new_rxns(model, adapter, inputs)
ecModel = fresh(model, adapter);

spec = inputs.new_reaction;
newRxns.rxns      = {spec.id};
newRxns.rxnNames  = {spec.name};
newRxns.equations = {spec.equation};
newRxns.grRules   = {spec.gr_rule};

% jsondecode turns a JSON array of objects into a MATLAB struct array, not a cell array
% of structs --- arrayfun, not cellfun.
enzSpecs = inputs.new_enzymes;
newEnzymes.enzymes = arrayfun(@(e) e.enzyme, enzSpecs, 'UniformOutput', false);
newEnzymes.genes   = arrayfun(@(e) e.gene,   enzSpecs, 'UniformOutput', false);
newEnzymes.mw      = arrayfun(@(e) e.mw,     enzSpecs);
newEnzymes.enzymes = newEnzymes.enzymes(:);
newEnzymes.genes   = newEnzymes.genes(:);
newEnzymes.mw      = newEnzymes.mw(:);

[ecModel, rxnsAdded, enzAdded] = addNewRxnsToEC(ecModel, newRxns, newEnzymes, adapter);

out.rxns_added = reshape(sort(rxnsAdded(:)), 1, []);
out.enz_added  = reshape(sort(enzAdded(:)), 1, []);
out.model      = model_summary(ecModel);
end


function out = model_summary(ecModel)
out.n_reactions   = numel(ecModel.rxns);
out.n_metabolites = numel(ecModel.mets);
out.n_genes       = numel(ecModel.genes);

[rxnIds, rxnOrder] = sort(ecModel.rxns(:));
reactions = cell(1, numel(rxnIds));
for k = 1:numel(rxnIds)
    i = rxnOrder(k);
    [lowerValue, lowerKind] = bound(ecModel.lb(i));
    [upperValue, upperKind] = bound(ecModel.ub(i));
    reactions{k} = struct( ...
        'id',                     rxnIds{k}, ...
        'lower_bound',            lowerValue, ...
        'lower_kind',             lowerKind, ...
        'upper_bound',            upperValue, ...
        'upper_kind',             upperKind, ...
        'objective_coefficient',  double(ecModel.c(i)));
end
out.reactions = reactions;

out.genes = reshape(sort(ecModel.genes(:)), 1, []);
out.gene_associations = pairs(ecModel.rxnGeneMat, ecModel.rxns, ecModel.genes, ...
    {'reaction', 'gene'}, false);
out.stoichiometry = pairs(ecModel.S.', ecModel.rxns, ecModel.mets, ...
    {'reaction', 'metabolite'}, true);

out.ec = ec_data(ecModel.ec);
end


function out = ec_data(ec)
% rxns/kcat/source/eccodes sorted by reaction id here, unlike ec_model_expansion_ectestgem's
% ec.rxns: *that* scenario's order is makeEcModel's own expansion order, which MATLAB's own
% unit tests pin exactly. The order addNewRxnsToEC appends new isozyme/reversibility variants
% in has no such contract on either side --- neither implementation's tests assert it --- so
% leaving it unsorted here would report an incidental loop-order difference as a finding.
[rxnIds, order] = sort(ec.rxns(:));
% Index the column form first, in the same shape as `order`, and only convert to blanks
% / reshape to a row afterwards --- indexing a row vector with a column index vector (or
% vice versa) returns a result shaped like the index, not like the thing indexed, which
% would silently do the wrong thing here.
kcat = double(ec.kcat(:)); kcat = kcat(order);
source = ec.source(:); source = source(order);
eccodes = ec.eccodes(:); eccodes = eccodes(order);

out.rxns    = reshape(rxnIds, 1, []);
out.genes   = reshape(ec.genes(:), 1, []);
out.enzymes = reshape(ec.enzymes(:), 1, []);
out.mw      = reshape(double(ec.mw(:)), 1, []);
out.eccodes = reshape(blanks_for_empty(eccodes), 1, []);
out.kcat    = reshape(kcat, 1, []);
out.source  = reshape(blanks_for_empty(source), 1, []);
out.coupling = pairs(ec.rxnEnzMat, ec.rxns, ec.enzymes, {'reaction', 'enzyme'}, true);
end


function [value, kind] = bound(x)
if isinf(x) && x > 0
    value = 0;
    kind = '+inf';
elseif isinf(x) && x < 0
    value = 0;
    kind = '-inf';
else
    value = double(x);
    kind = 'finite';
end
end


function out = pairs(matrix, rowIds, colIds, names, withCoefficient)
[rows, cols, values] = find(matrix);
keys = cell(numel(rows), 1);
for k = 1:numel(rows)
    keys{k} = [rowIds{rows(k)} char(1) colIds{cols(k)}];
end
[~, order] = sort(keys);

out = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    record = struct(names{1}, rowIds{rows(i)}, names{2}, colIds{cols(i)});
    if withCoefficient
        record.coefficient = double(values(i));
    end
    out{k} = record;
end
end


function out = blanks_for_empty(values)
out = values(:).';
for k = 1:numel(out)
    if isempty(out{k})
        out{k} = '';
    end
end
end
