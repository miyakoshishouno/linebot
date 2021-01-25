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
import os
import requests
import chart

app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
TALKAPI_KEY = os.environ['YOUR_API']


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



def talkapi(text):
   url = 'https://api.a3rt.recruit-tech.co.jp/talk/v1/smalltalk'
   req = requests.post(url, {'apikey':TALKAPI_KEY,'query':text}, timeout=5)
   data = req.json()

   if data['status'] != 0:
      return data['message']

   msg = data['results'][0]['reply']
   return msg


num = 0

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print(event)
    push_text = event.message.text
    print(push_text)
    str_1 = event.message.num
    print(str_1)
    array = []
    # global num

    # if num == 0:
    if push_text == "yes":
        print(push_text)
        # num = num + 1
        question = chart.judge(push_text,num)
        msg = make_button_template(question)

        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    elif push_text == "no":
        # num = num + 2
        question = "最初の質問"
        # question = chart.judge(push_text,num)
        msg = make_button_template(question)

        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    else:
        msg = "中断しました"
        num = 0

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg))

    # elif push_text == "チャート" and num == 0:
    #     num = 1
    #     question = "最初の質問" + str(num)
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


# Yes/Noチャート(確認テンプレート)
def make_button_template(question):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=question,
            actions=[
                MessageAction(
                    label = "Yes",
                    text  = "yes",
                    num = 1
                ),
                MessageAction(
                    label = "No",
                    text  = "No",
                    num = 2
                )
            ]
        )
    )
    return message_template