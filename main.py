from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,TemplateSendMessage,ConfirmTemplate,MessageAction
)

import psycopg2
from psycopg2.extras import DictCursor
import os
import requests
import chart

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
yoyaku_year = ""
yoyaku_month = ""
yoyaku_day = ""
yoyaku_time = ""
note = ""


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print(event.message.text)
    # print(event)
    # push_text = event.message.text
    # print(event)
    # array = []
    # global num
    # print("72行目"+str(num))
    # # 回数取得できた

    # if num > 0:
    #     if push_text == "Yes":
    #         num = num + 1
    #         print(num)
    #         # question = chart.judge(push_text,num)
    #         question = "最初の質問" + str(num)
    #         msg = make_button_template(question)

    #         line_bot_api.reply_message(
    #             event.reply_token,
    #             msg
    #         )

    #     elif push_text == "No":
    #         # num = num + 2
    #         question = "最初の質問" + str(num)
    #         # question = chart.judge(push_text,num)
    #         msg = make_button_template(question)

    #         line_bot_api.reply_message(
    #             event.reply_token,
    #             msg
    #         )

    #     else:
    #         msg = "中断しました"
    #         num = 0

    #         line_bot_api.reply_message(
    #             event.reply_token,
    #             TextSendMessage(text=msg))


    # elif push_text in "予約":
    #     num = 1
    #     question = "予約しますか？"
    #     msg = make_button_template(question)

    #     line_bot_api.reply_message(
    #         event.reply_token,
    #         msg
    #     )

    # else:
    #     msg = talkapi(push_text)

    #     line_bot_api.reply_message(
    #         event.reply_token,
    #         TextSendMessage(text=msg))

    rows = get_response_message(event.message.text)

    if len(rows)==0:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='no_data'))
    else:
        r = rows[0]
        reply_message = f'予約状況{r[1]}\n'\
            f'備考 {r[2]}\n'

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message))



def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


def get_response_message(mes_from):
    yoyaku_ymd = yoyaku_year + '/' + yoyaku_month + '/' + yoyaku_day + ' ' + yoyaku_time
    yoyaku_ymd = '2020/10/01 20:00:00'
    note = "ok"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # cur.execute("SELECT * FROM yoyaku_table")
            cur.execute("INSERT INTO yoyaku_table VALUES((SELECT max(id)+1 FROM  yoyaku_table),(%s,%s))",(yoyaku_ymd, note))
            conn.commit()
            # rows = cur.fetchall()
            # return rows



# Yes/Noチャート(確認テンプレート)
def make_button_template(question):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=question,
            actions=[
                MessageAction(
                    label = "Yes",
                    text  = "Yes"
                ),
                MessageAction(
                    label = "No",
                    text  = "No"
                )
            ]
        )
    )
    return message_template