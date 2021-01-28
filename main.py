from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,TemplateSendMessage,ConfirmTemplate,\
        MessageAction,DatetimePickerAction,PostbackEvent,ButtonsTemplate,PostbackTemplateAction,\
            QuickReply, QuickReplyButton,PostbackAction

)

import psycopg2
from psycopg2.extras import DictCursor
import os
import requests
import chart
import datetime

app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
TALKAPI_KEY = os.environ['YOUR_API']
DATABASE_URL = os.environ.get('DATABASE_URL')


line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


if __name__ == "__main__":
    app.run()
    port = int(os.getenv("PORT"))
    app.run(host="0.0.0.0", port=port)


# 日常会話API
def talkapi(text):
   url = 'https://api.a3rt.recruit-tech.co.jp/talk/v1/smalltalk'
   req = requests.post(url, {'apikey':TALKAPI_KEY,'query':text}, timeout=5)
   data = req.json()

   if data['status'] != 0:
      return data['message']

   msg = data['results'][0]['reply']
   return msg

# グローバル変数(会話のやりとりの保存)
num = 0
yoyaku_day = ""
yoyaku_time = ""
note = ""


@handler.add(MessageEvent, message=TextMessage)
# テキスト別に条件分岐
def handle_message(event):
    push_text = event.message.text

    if push_text in "予約":
        question = "予約しますか？"
        msg = make_button_template(question)
        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    elif push_text == "create_yoyaku":
        label = "日付を選択してください。"
        msg  = make_button_template2(label)
        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    elif push_text == "show_yoyaku":
        rows = get_response_message()

        if len(rows)==0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='現在予約はありません。'))
        else:
            reply_message = ""
            for i in range(len(rows)):
                r = rows[i]
                reply_message += '予約状況 :' + (str(r[1]).replace('-','/'))[:-3] + '\n備考 :' + r[2] + '\n'

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_message))

    else:
        msg = talkapi(push_text)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg))


# db接続
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


# 予約一覧表示処理
def get_response_message():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM yoyaku_table")
            rows = cur.fetchall()
            return rows


# 新規登録処理
def add_response_message(yoyaku_data):
    note = "ok"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO yoyaku_table VALUES((select max(id)+1 from  yoyaku_table),%s,%s)",(yoyaku_data, note))
            conn.commit()


# Yes/Noチャート(確認テンプレート)
def make_button_template(question):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=question,
            actions=[
                MessageAction(
                    label = "予約する",
                    text  = "create_yoyaku"
                ),
                MessageAction(
                    label = "予約状況確認",
                    text  = "show_yoyaku"
                )
            ]
        )
    )
    return message_template

# 日付ボタン
def make_button_template2(label):
    # 現在日時の取得
    get_day = datetime.datetime.now()
    get_date = str(get_day.year) + "-" + str(get_day.month).zfill(2) + "-" + str(get_day.day).zfill(2)

    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=label,
            actions=[
                DatetimePickerAction(
                    type = "datetimepicker",
                    label = "Select date",
                    data = "storeId=12345",
                    mode = "date",
                    initial = get_date,
                    max = "2088-01-24",
                    min = get_date
                ),
                MessageAction(
                    label = "予約状況確認",
                    text  = "show_yoyaku"
                )
            ]
        )
    )
    return message_template

# 時刻
def make_button_template3(label):
    # 現在日時の取得
    get_day = datetime.datetime.now()
    get_date = str(get_day.hour + 9).zfill(2) + ":00"

    quick_reply=QuickReply(
        text=label,
        items=[
            QuickReplyButton(
                action=PostbackAction(label="10:00~", data="10:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="11:00~", data="11:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="12:00~", data="12:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="13:00~", data="13:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="14:00~", data="14:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="15:00~", data="15:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="16:00~", data="16:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="17:00~", data="17:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="18:00~", data="18:00")
            ),
            QuickReplyButton(
                action=PostbackAction(label="19:00~", data="19:00")
            )
        ]
    )
    return quick_reply



@handler.add(PostbackEvent)
def on_postback(event):
    if isinstance(event, PostbackEvent):
        global yoyaku_day
        if event.postback.params is not None:
            yoyaku_day = (event.postback.params['date'])[:4] + "/" + (event.postback.params['date'])[5:7] + "/" + (event.postback.params['date'])[8:]   
            label = (yoyaku_day + "ですね。\n　希望する時間帯を選択してください。")
            msg  = make_button_template3(label)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(quick_reply=msg)

        elif event.postback.data is not None:
            yoyaku_date = str(yoyaku_day) + " " + str(event.postback.data) + ":00"
            print("予約日",yoyaku_date)
            add_response_message(yoyaku_date)
            msg = yoyaku_date[:-3] + "で予約を完了しました。\n予約状況は、予約一覧から確認できます。"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg))  
            # if event.postback.data == "異性に質問してみる":
            #     print("ここです")