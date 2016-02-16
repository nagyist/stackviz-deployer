'use strict';

var debounce = function(func, delay) {
  var timeoutId = null;

  return function() {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(function(context) {
      func.apply(context, arguments);
    }, delay, this);
  };
};

$(document).ready(function() {
  var examples = [
    'https://review.openstack.org/#/c/271726/',
    '271726',
    '271726,1',
    'http://logs.openstack.org/26/271726/2/check/gate-stackviz-python27/99349a5/'
  ];

  var input = $('#input');
  var button = $('#button');
  var results = $('#results');
  var resultsContainer = $('#results-container');
  var resultsError = $('#results-error');

  var showExample = function() {
    var ex = examples[Math.floor(Math.random() * examples.length)];
    input.attr('placeholder', 'e.g. ' + ex);
  };

  var createResultRow = function(artifact) {
    var row = $('<div>', { 'class': 'row' });
    var col = $('<div>', { 'class': 'col-md-12' });

    var panel = $('<div>', { 'class': 'panel'});
    if (artifact.status === 'success') {
      panel.addClass('panel-success');
    } else if (artifact.status === 'failed') {
      panel.addClass('panel-danger');
    } else {
      panel.addClass('panel-default');
    }

    var heading = $('<div>', { 'class': 'panel-heading' });
    heading.append($('<h3>', {
      'class': 'panel-title',
      'text': artifact.change_subject + ' - ' +
        ' (' + artifact.change_project + ' #' +
        artifact.change_id + ',' + artifact.revision + ' - ' +
        artifact.ci_username + ' ' + artifact.pipeline + ')'
    }));
    panel.append(heading);

    var list = $('<ul>', { 'class': 'list-group' });
    artifact.jobs.forEach(function(job, i) {
      var item = $('<li>', {
        'class': 'list-group-item',
        'text': job.name + ' (' + job.status + ')'
      });

      if (job.status === 'FAILURE') {
        item.addClass('list-group-item-danger');
      }

      list.append(item);
    });
    panel.append(list);

    col.append(panel);
    row.append(col);
    return row;
  };

  var updateResults = function(data) {
    results.show();

    if (data.results.length === 0) {
      resultsError.show();
      resultsContainer.hide();
      return;
    }

    resultsError.hide();
    resultsContainer.show();

    resultsContainer.empty();
    data.results.forEach(function(r, i) {
      var row = createResultRow(r);

      resultsContainer.append(row);
    });
  };

  var fetchResults = function() {
    results.hide();

    var q = input.val();
    if (!q || !q.trim()) {
      results.hide();
      return;
    }

    $.ajax({
      url: '/api/list',
      type: 'POST',
      contentType: 'application/json;  charset=utf-8',
      dataType: 'json',
      data: JSON.stringify({ q: input.val() }),
      success: function(data) {
        updateResults(data);
      }
    });
  };

  input.on('input', debounce(fetchResults, 500));
  button.on('click', fetchResults);

  setInterval(showExample, 3000);
  showExample();
});
