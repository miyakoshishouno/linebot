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
from datetime import time

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
            cur.execute("SELECT * FROM yoyaku_table ORDER BY id DESC  LIMIT 5")
            rows = cur.fetchall()
            return rows


# 新規登録処理
def add_response_message(yoyaku_data):
    note = "ok"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO yoyaku_table VALUES((select max(id)+1 from  yoyaku_table),%s,%s)",(yoyaku_data, note))
            conn.commit()

# 削除処理
def del_response_message(yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("DELETE FROM yoyaku_table WHERE id = (%s)",(yoyaku_id))
            conn.commit()



# 予約ボタン
def make_button_template(question):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=question,
            actions=[
                PostbackAction(
                    label = "予約する",
                    data  = "create_yoyaku"
                ),
                PostbackAction(
                    label = "予約状況確認",
                    data  = "menu_yoyaku"
                )
            ]
        )
    )
    return message_template

# 予約確認/予約削除ボタン
def button_show_or_del(label):

    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=label,
            actions=[
                PostbackAction(
                    label = "予約一覧",
                    data  = "show_yoyaku"
                ),
                PostbackAction(
                    label = "予約削除",
                    data  = "del_yoyaku"
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
                    label = "日付選択",
                    data = "storeId=12345",
                    mode = "date",
                    initial = get_date,
                    max = "2088-01-24",
                    min = get_date
                ),
                PostbackAction(
                    label = "予約状況確認",
                    data  = "menu_yoyaku"
                )
            ]
        )
    )
    return message_template



# 時刻選択ボタン
def make_button_template3():
    # 現在日時の取得
    get_day = datetime.datetime.now()
    get_now = str(get_day.year) +'/' +  str(get_day.month).zfill(2) + '/' + str(get_day.day).zfill(2)
    get_date = str(get_day.hour + 9).zfill(2) + ":00:00"
    # 時間によってボタンの数を変更
    global yoyaku_day
    item_list = []
    time_list = [10,11,12,13,14,15,16,17,18,19]

    #当日の場合
    if yoyaku_day == get_now:
        for i in range(len(time_list)):
            if time(int(str(get_day.hour + 9).zfill(2)),00,00) < time(time_list[i],00,00):
                item_list.append(QuickReplyButton(\
                    action=PostbackAction(label= str(time_list[i]) + ":00~", data= str(time_list[i]) + ":00")))
        print(item_list)

    else:
        for i in range(len(time_list)):
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= str(time_list[i]) + ":00~", data= str(time_list[i]) + ":00")))
        print(item_list)

    quick_reply=QuickReply(items = item_list)
    return quick_reply



# 削除確認ボタン
def button_del_kakunin():
    rows = get_response_message()
    item_list = []
    if len(rows):
        for i in range(len(rows)):
            r = rows[i]
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= (str(r[1]).replace('-','/'))[:-3], data= "id_" + str(r[0]))))

        item_list.append(QuickReplyButton(\
            action=PostbackAction(label= "戻る", data= "id_cancel")))


    quick_reply=QuickReply(items = item_list)
    return quick_reply



@handler.add(PostbackEvent)
def on_postback(event):
    if isinstance(event, PostbackEvent):
        global yoyaku_day
        if event.postback.params is not None:
            yoyaku_day = (event.postback.params['date'])[:4] + "/" + (event.postback.params['date'])[5:7] + "/" + (event.postback.params['date'])[8:]   
            label = (yoyaku_day + "ですね。\n希望する時間帯を選択してください。")
            msg  = make_button_template3()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=label,quick_reply=msg)
            )


        elif event.postback.data is not None:
            if event.postback.data == 'menu_yoyaku':
                print("menu処理")
                label = "どちらか選択してください。"
                msg = button_show_or_del(label)
                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )


            elif event.postback.data == 'create_yoyaku':
                print("予約処理")
                label = "日付を選択してください。"
                msg  = make_button_template2(label)
                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )


            elif event.postback.data == 'show_yoyaku':
                print("一覧表示処理")
                rows = get_response_message()

                if len(rows)==0:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='現在予約はありません。'))
                else:
                    reply_message = '現在の予約状況は以下になります。(最新5件を表示)'
                    for i in range(len(rows)):
                        r = rows[i]
                        reply_message += '\n予約状況 :' + (str(r[1]).replace('-','/'))[:-3] + '\n備考 :' + r[2]

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=reply_message))


            elif event.postback.data == 'del_yoyaku':
                print("削除処理確認")
                label = "削除する項目を選択してください。(最新5件を表示)"
                msg = button_del_kakunin()
                if len(msg.items) != 0:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=label,quick_reply=msg)
                    )
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='現在予約はありません。'))
            

            elif event.postback.data.startswith('id_'):
                if event.postback.data[3:] == "cancel":
                    label = "どちらか選択してください。"
                    msg = button_show_or_del(label)
                    line_bot_api.reply_message(
                        event.reply_token,
                        msg
                    )

                else:
                    print(event.postback.data)
                    yoyaku_id = event.postback.data[3:]
                    del_response_message(yoyaku_id)
                    msg = "削除が完了しました。"
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=msg)
                    )


            else:
                yoyaku_date = str(yoyaku_day) + " " + str(event.postback.data) + ":00"
                print("予約日",yoyaku_date)
                add_response_message(yoyaku_date)
                msg = yoyaku_date[:-3] + "で予約を完了しました。\n予約状況は、予約一覧から確認できます。"

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=msg)
                )