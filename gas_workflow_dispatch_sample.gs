/**
 * GitHub Actions「workflow_dispatch」（雑貨: threads_zakka）
 * classic PAT に workflow 権限が必要。
 * GITHUB_TOKEN に自分のトークンを入れる。
 */
var GITHUB_TOKEN = "";
var REPO = "travelj0907/threads_zakka";
var WORKFLOW = "auto_post.yml";

function triggerPost() {
  var url =
    "https://api.github.com/repos/" +
    REPO +
    "/actions/workflows/" +
    WORKFLOW +
    "/dispatches";
  var options = {
    method: "post",
    headers: {
      Authorization: "token " + GITHUB_TOKEN,
      Accept: "application/vnd.github.v3+json",
    },
    contentType: "application/json",
    payload: JSON.stringify({ ref: "main" }),
    muteHttpExceptions: true,
  };
  var res = UrlFetchApp.fetch(url, options);
  Logger.log(res.getResponseCode() + ": " + res.getContentText());
}

// 一度だけ実行してトリガーをまとめて作成する
function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    ScriptApp.deleteTrigger(t);
  });

  var hours = [8, 12, 18, 20];
  hours.forEach(function (h) {
    ScriptApp.newTrigger("triggerPost")
      .timeBased()
      .atHour(h)
      .everyDays(1)
      .inTimezone("Asia/Tokyo")
      .create();
  });

  Logger.log("トリガーを4つ作成しました: " + hours.join("時 / ") + "時");
}
