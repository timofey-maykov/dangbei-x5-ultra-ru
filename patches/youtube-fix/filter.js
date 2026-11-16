// Local YouTube TV response filter. No remote code or extra network requests.
// Injection approach: ysamjo/morphe-patches and jair1c/farotv-patches (GPL-3.0).
(function () {
  'use strict';
  if (location.hostname !== 'www.youtube.com' || !/^\/tv(?:\/|$)/.test(location.pathname)) return;
  if (window.__ytFixAds) return;
  var stats = window.__ytFixAds = {responses: 0, schedules: 0, tiles: 0};
  var keys = ['adPlacements', 'adSlots', 'playerAds', 'adBreakHeartbeatParams'];
  var tiles = ['adSlotRenderer', 'inFeedAdLayoutRenderer', 'promotedVideoRenderer',
    'compactPromotedVideoRenderer', 'promotedSparklesWebRenderer'];
  var own = Object.prototype.hasOwnProperty;
  var parse = JSON.parse;
  function report() {
    document.title = 'ytfix:responses=' + stats.responses + ',schedules=' + stats.schedules + ',tiles=' + stats.tiles;
  }
  function adItem(value) {
    return value && typeof value === 'object' && tiles.some(function (key) { return own.call(value, key); });
  }
  function clean(value, depth) {
    if (!value || typeof value !== 'object' || depth > 45) return value;
    if (Array.isArray(value)) {
      for (var i = value.length - 1; i >= 0; i--) {
        if (adItem(value[i])) { value.splice(i, 1); stats.tiles++; }
        else clean(value[i], depth + 1);
      }
    } else {
      keys.forEach(function (key) {
        if (own.call(value, key)) { delete value[key]; stats.schedules++; }
      });
      Object.keys(value).forEach(function (key) { clean(value[key], depth + 1); });
    }
    return value;
  }
  JSON.parse = function () {
    var value = parse.apply(this, arguments);
    var text = arguments[0];
    if (typeof text !== 'string' || !/(adPlacements|adSlots|playerAds|adBreakHeartbeatParams|adSlotRenderer|inFeedAdLayoutRenderer|promotedVideoRenderer|compactPromotedVideoRenderer|promotedSparklesWebRenderer)/.test(text)) return value;
    stats.responses++;
    clean(value, 0);
    report();
    return value;
  };
  if (window.Response && Response.prototype.json) {
    var responseJson = Response.prototype.json;
    Response.prototype.json = function () {
      return responseJson.apply(this, arguments).then(function (value) {
        var before = stats.schedules + stats.tiles;
        clean(value, 0);
        if (before !== stats.schedules + stats.tiles) { stats.responses++; report(); }
        return value;
      });
    };
  }
  if (window.ytInitialPlayerResponse) clean(window.ytInitialPlayerResponse, 0);
  report();
}());
