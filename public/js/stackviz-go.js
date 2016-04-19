'use strict';

var GERRIT_BASE = 'https://review.openstack.org/#/c/';

function gerritUrl(artifact) {
  return GERRIT_BASE + artifact.change_id + '/' + artifact.revision;
}

$(document).ready(function() {
  var results = $('#results');
  var resultsContainer = $('#results-container');
  var resultsError = $('#results-error');
  var status = $('#status');
  var statusMessage = $('#status-message');
  var statusJob = $('#status-job');
  var statusGerrit = $('#status-gerrit');
  var statusUuid = $('#status-uuid');

  var checkStatus = function(uuid) {
    $.ajax({
      url: '/api/status',
      type: 'POST',
      contentType: 'application/json;  charset=utf-8',
      dataType: 'json',
      data: JSON.stringify({ q: uuid }),
      success: function(data) {
        var text = data.status;
        if (text === 'error' && data.message) {
          text += ': ' + data.message;

          statusMessage.addClass('text-danger');
        }
        statusMessage.text(text);

        if (data.status.toLowerCase() === 'finished') {
          statusMessage.text('redirecting...');

          setTimeout(function() {
            window.location.assign('/s/' + uuid + '/');
          }, 1000);
        } else if (data.status.toLowerCase() !== 'error') {
          setTimeout(function() {
            checkStatus(uuid);
          }, 1000);
        }
      }
    });
  };

  var requestScrape = function(artifact, job) {
    status.show();
    statusMessage.text('initializing...');
    statusJob.attr('href', job.url);
    statusJob.text(job.url);
    statusGerrit.attr('href', gerritUrl(artifact));
    statusGerrit.text(gerritUrl(artifact));

    $.ajax({
      url: '/api/scrape',
      type: 'POST',
      contentType: 'application/json;  charset=utf-8',
      dataType: 'json',
      data: JSON.stringify({
        change_id: artifact.change_id,
        change_project: artifact.change_project,
        change_subject: artifact.change_subject,
        ci_username: artifact.ci_username,
        name: job.name,
        pipeline: artifact.pipeline,
        revision: artifact.revision,
        status: job.status,
        url: job.url
      }),
      success: function(data) {
        statusUuid.text(data.uuid);
        checkStatus(data.uuid);
      }
    });
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

    var list = $('<div>', { 'class': 'list-group' });
    artifact.jobs.forEach(function(job, i) {
      var item = $('<a>', {
        'class': 'list-group-item',
        'text': job.name + ' (' + job.status + ')'
      });

      item.click(function() {
        requestScrape(artifact, job);
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
    if (data.results.length === 0) {
      results.show();
      resultsError.show();
      resultsContainer.hide();
    } else if (data.results.length === 1 &&
               data.results[0].jobs.length === 1) {
      var result = data.results[0];
      var job = result.jobs[0];
      requestScrape(result, job);
    } else {
      results.show();
      resultsError.hide();
      resultsContainer.show();

      resultsContainer.empty();
      data.results.forEach(function(r, i) {
        var row = createResultRow(r);

        resultsContainer.append(row);
      });
    }
  };

  var fetchResults = function() {
    results.hide();

    var q = window.location.pathname.substring(4);
    if (window.location.hash) {
      q += window.location.hash;
    }

    if (!q || !q.trim()) {
      results.hide();
      return;
    }

    $.ajax({
      url: '/api/list',
      type: 'POST',
      contentType: 'application/json;  charset=utf-8',
      dataType: 'json',
      data: JSON.stringify({ q: q }),
      success: function(data) {
        updateResults(data);
      }
    });
  };

  fetchResults();
});
