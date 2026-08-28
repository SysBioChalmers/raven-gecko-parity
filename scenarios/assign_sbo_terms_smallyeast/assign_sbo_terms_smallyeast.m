function results = assign_sbo_terms_smallyeast(ctx)
% MATLAB side of the SBO-term-assignment scenario.
%
% assignSBOterms's transport detection (getTransportRxns) flags a
% reaction whenever the same metabolite NAME appears more than once among
% its participants, with no regard for compartment; add_sbo_terms's own
% default detector is explicitly documented as "a cheap analogue" that
% instead requires the name to appear in >= 2 DISTINCT compartments. The
% two agree on any model with no same-name-same-compartment duplicate
% metabolites --- true of smallYeast, checked directly against its own
% metabolite list before this file was written --- and would diverge only
% on a model that has one. Not exercised here; see scenario.yml.
%
% biomass_rxn_name / ngam_rxn_name are redirected to real smallYeast
% reaction names (their yeast-GEM-specific defaults match nothing here)
% so those two override branches, and their priority over the
% single-reactant default, are actually exercised: biomassOUT starts
% single-reactant (sink, by its negative coefficient) and ends up
% reclassified to the biomass-reaction term instead.

inputs = ctx.inputs;
model = readYAMLmodel(inputs.model);

opts.biomassRxnName = char(inputs.biomass_rxn_name);
opts.ngamRxnName = char(inputs.ngam_rxn_name);
model = assignSBOterms(model, 'opts', opts);

metRecords = cell(1, numel(model.mets));
for i = 1:numel(model.mets)
    metRecords{i} = struct('metabolite', model.mets{i}, 'sbo', read_sbo(model.metMiriams{i}));
end
[~, order] = sort(model.mets);
results.metabolite_sbo = metRecords(order);

rxnRecords = cell(1, numel(model.rxns));
for i = 1:numel(model.rxns)
    rxnRecords{i} = struct('reaction', model.rxns{i}, 'sbo', read_sbo(model.rxnMiriams{i}));
end
[~, order] = sort(model.rxns);
results.reaction_sbo = rxnRecords(order);

end


function sbo = read_sbo(miriam)
sbo = '';
if isempty(miriam) || ~isfield(miriam, 'name')
    return
end
i = find(strcmp(miriam.name, 'sbo'), 1);
if ~isempty(i)
    sbo = miriam.value{i};
end
end
