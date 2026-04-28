/**
 * GitHub Actions「workflow_dispatch」用サンプル（雑貨: threads_zakka）
 *
 * 使い方:
 * 1. スクリプト プロパティに GITHUB_TOKEN（classic PAT: workflow 権限）を保存
 * 2. triggerPost をテスト実行 → 200 でワークフローが走れば OK
 * 3. setupTriggers で東京時間の毎日トリガー（必要なら hours を編集）
 *
 * 注意: トークンをソースに直書きしないこと。流出した ghp_ は GitHub で失効させる。
 */
var REPO = "travelj0907/threads_zakka";
var WORKFLOW = "auto_post.yml";

function getToken_() {
  var t = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  if (!t) throw new Error("スクリプト プロパティに GITHUB_TOKEN を設定してください");
  return t;
}

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
      Authorization: "token " + getToken_(),
      Accept: "application/vnd.github+json",
    },
    contentType: "application/json",
    payload: JSON.stringify({ ref: "main" }),
    muteHttpExceptions: true,
  };
  var res = UrlFetchApp.fetch(url, options);
  Logger.log(res.getResponseCode() + ": " + res.getContentText());
}

/** 既存トリガーを消して、東京時間で毎日同じ時刻に triggerPost */
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

  Logger.log("トリガー作成: 東京 " + hours.join("時 / ") + "時（毎日）");
}
