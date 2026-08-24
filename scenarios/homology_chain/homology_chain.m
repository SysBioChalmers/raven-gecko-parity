function results = homology_chain(ctx)
% MATLAB side of the homology chain.
%
% Must return exactly the shape run.py returns --- same field names, same
% ordering rules --- because `parity compare` diffs the two structurally. Where
% the toolboxes disagree that is the finding; where this file and run.py
% disagree that is a bug here.
%
% Conventions that matter, all of them the easy way to a false difference:
%   * sorting --- every list is sorted by id, never left in model order;
%   * lists of structs --- reaction ids are not valid MATLAB field names, so
%     records are cell arrays of structs rather than keyed objects;
%   * GPRs as DNF clauses --- `A or B` and `B or A` must compare equal;
%   * braces belong inside struct(...) calls, where a cell value would otherwise
%     build a struct *array*; a plain dot assignment takes the cell array as it
%     is. Wrapping there instead produces a 1x1 cell holding the whole list, and
%     every list arrives at the comparison with length 1.

results.blast = blast_checkpoint(ctx.inputs);
results.draft = draft_checkpoint(ctx.inputs);

end


function out = blast_checkpoint(inputs)
% getBlast hardcodes -evalue 10e-5; the scenario passes the same value to the
% Python side rather than letting each use its own default.
blastStructure = getBlast( ...
    inputs.query_id, inputs.query_fasta, ...
    {inputs.ref_id}, {inputs.ref_fasta});

records = {};
for i = 1:numel(blastStructure)
    entry = blastStructure(i);
    for k = 1:numel(entry.fromGenes)
        records{end+1} = struct( ...
            'from_id',   char(entry.fromId), ...
            'to_id',     char(entry.toId), ...
            'from_gene', char(entry.fromGenes{k}), ...
            'to_gene',   char(entry.toGenes{k}), ...
            'evalue',    double(entry.evalue(k)), ...
            'identity',  double(entry.identity(k)), ...
            'align_len', double(entry.aligLen(k)), ...
            'bitscore',  double(entry.bitscore(k)), ...
            'ppos',      double(entry.ppos(k))); %#ok<AGROW>
    end
end

records = sort_records(records, {'from_id', 'to_id', 'from_gene', 'to_gene'});

% Per-direction counts, in the same sorted order the Python side emits.
directionKeys = {};
directionCounts = [];
for k = 1:numel(records)
    key = [records{k}.from_id '|' records{k}.to_id];
    idx = find(strcmp(directionKeys, key), 1);
    if isempty(idx)
        directionKeys{end+1} = key; %#ok<AGROW>
        directionCounts(end+1) = 1; %#ok<AGROW>
    else
        directionCounts(idx) = directionCounts(idx) + 1;
    end
end
[directionKeys, order] = sort(directionKeys);
directionCounts = directionCounts(order);

directions = cell(1, numel(directionKeys));
for k = 1:numel(directionKeys)
    parts = strsplit(directionKeys{k}, '|');
    directions{k} = struct( ...
        'from_id', parts{1}, ...
        'to_id',   parts{2}, ...
        'n_hits',  directionCounts(k));
end

out.n_hits = numel(records);
out.directions = directions;
out.hits = records;
end


function out = draft_checkpoint(inputs)
template = readYAMLmodel(inputs.model);
template.id = char(inputs.source_model_id);

% Sorted, not model order: the two toolboxes need not store genes the same way
% and the ortholog mapping must not depend on that.
sourceGenes = sort(template.genes);
n = min(double(inputs.ortholog_count), numel(sourceGenes));
sourceGenes = sourceGenes(1:n);
targetGenes = strcat('t_', sourceGenes);

orthologList = [sourceGenes(:), targetGenes(:)];
blastStructure = makeFakeBlastStructure( ...
    orthologList, char(inputs.source_model_id), char(inputs.target_organism_id));

evalc('draft = getModelFromHomology({template}, blastStructure, char(inputs.target_organism_id));');

pairs = cell(1, n);
for k = 1:n
    pairs{k} = struct('source', sourceGenes{k}, 'target', targetGenes{k});
end

out.n_reactions = numel(draft.rxns);
out.n_metabolites = numel(draft.mets);
out.n_genes = numel(draft.genes);
out.ortholog_pairs = pairs;
out.reactions = sort(draft.rxns(:))';
out.metabolites = sort(draft.mets(:))';
out.genes = sort(draft.genes(:))';
out.gene_rules = gene_rules(draft);
out.stoichiometry = stoichiometry(draft);
end


function rules = gene_rules(model)
% GPRs as sorted DNF clauses, matching run.py's gpr_to_dnf output.
[sortedRxns, order] = sort(model.rxns);
rules = cell(1, numel(sortedRxns));

for k = 1:numel(sortedRxns)
    rule = '';
    if isfield(model, 'grRules')
        rule = model.grRules{order(k)};
    end

    clauses = {};
    if ~isempty(rule)
        % grRuleToDNF already returns one cell array of gene ids per AND-clause
        % --- the same shape gpr_to_dnf gives the Python side --- so there is no
        % rule string to parse back apart.
        dnf = grRuleToDNF(rule);
        clauses = cell(1, numel(dnf));
        for c = 1:numel(dnf)
            genes = dnf{c};
            clauses{c} = sort(genes(:))';
        end
        clauses = sort_clauses(clauses);
    end

    rules{k} = struct('reaction', sortedRxns{k}, 'clauses', {clauses});
end
end


function entries = stoichiometry(model)
[rowIdx, colIdx, coeffs] = find(model.S);
entries = cell(1, numel(coeffs));
for k = 1:numel(coeffs)
    entries{k} = struct( ...
        'reaction',    model.rxns{colIdx(k)}, ...
        'metabolite',  model.mets{rowIdx(k)}, ...
        'coefficient', double(coeffs(k)));
end
entries = sort_records(entries, {'reaction', 'metabolite'});
end


function records = sort_records(records, fields)
% Sort a cell array of structs by the named char fields, in order.
if isempty(records)
    return
end
keys = cell(1, numel(records));
for k = 1:numel(records)
    parts = cell(1, numel(fields));
    for f = 1:numel(fields)
        parts{f} = records{k}.(fields{f});
    end
    keys{k} = strjoin(parts, char(0));
end
[~, order] = sort(keys);
records = records(order);
end


function clauses = sort_clauses(clauses)
% Sort clauses by their joined gene names, so clause order carries no meaning.
if isempty(clauses)
    return
end
keys = cellfun(@(c) strjoin(c, char(0)), clauses, 'UniformOutput', false);
[~, order] = sort(keys);
clauses = clauses(order);
end
