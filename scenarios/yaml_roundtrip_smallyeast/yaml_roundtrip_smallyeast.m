function results = yaml_roundtrip_smallyeast(ctx)
% MATLAB side of the YAML reader/writer scenario.
%
% Same three checkpoints as run.py. Both writes go to a temporary file rather
% than into the repository --- what is being compared is what the writer
% produces, not an artefact anyone needs to keep.
%
% Line endings are normalised to \n before the text is emitted: fopen in text
% mode writes CRLF on Windows, which is a property of this harness rather than
% of writeYAMLmodel.

source = ctx.inputs.model;

direct = readYAMLmodel(source);

workdir = tempname;
mkdir(workdir);
cleanup = onCleanup(@() rmdir(workdir, 's'));

asReadFile = fullfile(workdir, 'as_read.yml');
sortedFile = fullfile(workdir, 'sorted.yml');
writeYAMLmodel(direct, 'fileName', asReadFile);
writeYAMLmodel(direct, 'fileName', sortedFile, 'sortIds', true);

written.as_read = file_record(asReadFile);
written.sorted = file_record(sortedFile);

reread = readYAMLmodel(asReadFile);

directSummary = summary(direct);
roundtripSummary = summary(reread);

results.direct = directSummary;
results.written = written;

results.roundtrip = roundtripSummary;
% This implementation's own verdict on its round trip. Both sides reporting
% false is not a match in any useful sense, which is why the summary travels
% with it.
results.roundtrip.identical_to_direct = isequal(roundtripSummary, directSummary);

end


function record = file_record(path)
text = fileread(path);
text = strrep(text, sprintf('\r\n'), sprintf('\n'));
lines = strsplit(text, sprintf('\n'), 'CollapseDelimiters', false);
% A trailing newline is a property of the file, not a final empty line.
if ~isempty(lines) && isempty(lines{end})
    lines(end) = [];
end

record.n_lines = numel(lines);
record.n_chars = sum(cellfun(@numel, lines));
record.lines = row(lines);
end


function out = summary(model)
out.model_id = char_or_empty(model, 'id');
out.model_name = char_or_empty(model, 'name');
out.n_reactions = numel(model.rxns);
out.n_metabolites = numel(model.mets);
if isfield(model, 'genes')
    out.n_genes = numel(model.genes);
else
    out.n_genes = 0;
end

out.compartments = compartment_records(model);
out.reactions = reaction_records(model);
out.metabolites = metabolite_records(model);
if isfield(model, 'genes')
    out.genes = row(sort(model.genes(:)));
else
    out.genes = {};
end
out.gene_rules = gene_rules(model);
out.stoichiometry = stoichiometry(model);
end


function records = compartment_records(model)
[~, order] = sort(model.comps);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    if isfield(model, 'compNames') && numel(model.compNames) >= i
        name = model.compNames{i};
    else
        name = '';
    end
    records{k} = struct('id', model.comps{i}, 'name', name);
end
end


function records = reaction_records(model)
[~, order] = sort(model.rxns);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'id', model.rxns{i}, ...
        'name', model.rxnNames{i}, ...
        'lower_bound', double(model.lb(i)), ...
        'upper_bound', double(model.ub(i)), ...
        'objective_coefficient', double(model.c(i)));
end
end


function records = metabolite_records(model)
[~, order] = sort(model.mets);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);

    % A missing charge is a flag plus a zero rather than NaN: jsonencode
    % writes NaN as null while the Python side writes the string "NaN", so an
    % absent charge would otherwise read as a difference between the two
    % harnesses instead of as the absence it is.
    charge = 0;
    hasCharge = false;
    if isfield(model, 'metCharges') && numel(model.metCharges) >= i && ~isnan(model.metCharges(i))
        charge = double(model.metCharges(i));
        hasCharge = true;
    end

    records{k} = struct( ...
        'id', model.mets{i}, ...
        'name', model.metNames{i}, ...
        'compartment', model.comps{model.metComps(i)}, ...
        'formula', model.metFormulas{i}, ...
        'has_charge', hasCharge, ...
        'charge', charge);
end
end


function records = gene_rules(model)
[~, order] = sort(model.rxns);
records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    if isfield(model, 'grRules')
        clauses = grRuleToDNF(model.grRules{i});
    else
        clauses = {};
    end

    clauses = clauses(:)';
    keys = cell(1, numel(clauses));
    for j = 1:numel(clauses)
        clauses{j} = row(sort(clauses{j}(:)));
        keys{j} = join_key(clauses{j});
    end
    if ~isempty(clauses)
        [~, clauseOrder] = sort(keys);
        clauses = clauses(clauseOrder);
    end

    records{k} = struct('reaction', model.rxns{i}, 'clauses', {clauses});
end
end


function records = stoichiometry(model)
[rowIdx, colIdx, coefficients] = find(model.S);

keys = cell(numel(rowIdx), 1);
for k = 1:numel(rowIdx)
    keys{k} = join_key({model.rxns{colIdx(k)}, model.mets{rowIdx(k)}});
end
[~, order] = sort(keys);

records = cell(1, numel(order));
for k = 1:numel(order)
    i = order(k);
    records{k} = struct( ...
        'reaction', model.rxns{colIdx(i)}, ...
        'metabolite', model.mets{rowIdx(i)}, ...
        'coefficient', double(coefficients(i)));
end
end


function key = join_key(parts)
% char(1) sorts below every character an identifier can contain, so joining on
% it orders exactly as Python's tuple comparison does --- including the case
% where one key is a prefix of another.
key = strjoin(parts(:)', char(1));
end


function value = char_or_empty(model, field)
if isfield(model, field) && ~isempty(model.(field))
    value = char(model.(field));
else
    value = '';
end
end


function out = row(values)
out = reshape(values, 1, []);
if isempty(out)
    out = {};
end
end
