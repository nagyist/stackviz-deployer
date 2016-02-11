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
  var resultsRow = $('#results-row');
  var resultsList = $('#results-list');
  var resultsError = $('#results-error');

  var showExample = function() {
    var ex = examples[Math.floor(Math.random() * examples.length)];
    input.attr('placeholder', 'e.g. ' + ex);
  };

  var updateResults = function(data) {
    resultsRow.show();

    if (!data.results) {
      resultsError.show();
      resultsList.hide();
      return;
    }

    resultsError.hide();
    resultsList.show();

    resultsList.empty();
    data.results.forEach(function(r, i) {
      var item = $('<a>', {
        'class': 'list-group-item'
      });

      if (r.status === 'FAILURE') {
        item.addClass('list-group-item-danger');
      } else if (r.status === 'SUCCESS') {
        item.addClass('list-group-item-success');
      }

      item.append($('<h4>', {
        'class': 'list-group-item-heading',
        'text': r.name + ' (' + r.change_project + ' #' + r.change_id + ',' + r.revision + ')'
      }));

      var text = $('<p>', {'class': 'list-group-item-text'}).appendTo(item);

      var textList = $('<ul>').appendTo(text);

      textList.append($('<li>Status: ' + r.status + '</li>'));

      if (r.pipeline) {
        textList.append($('<li>Pipeline: ' + r.pipeline + '</li>'));
      }

      if (r.ci_username) {
        textList.append($('<li>CI User: ' + r.ci_username + '</li>'));
      }

      resultsList.append(item);
    });
  };

  var fetchResults = function() {
    resultsRow.hide();

    var q = input.val();
    if (!q || !q.trim()) {
      resultsRow.hide();
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

  input.on('keyup', debounce(fetchResults, 500));
  button.on('click', fetchResults);

  setInterval(showExample, 3000);
  showExample();
});
