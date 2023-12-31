from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import urllib.request
import requests
from urllib.parse import quote
import pandas as pd
import numpy as np
import joblib

import numpy as np
import pytesseract
from pytesseract import Output
from PIL import Image
from io import BytesIO 

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

from sklearn.preprocessing import StandardScaler

app = Flask(__name__)
CORS(app, supports_credentials=True)

이미지 텍스트 추출
def extract_text(img_url):
    config = ('-l kor+eng')
    
    response = requests.get(img_url)
    img = Image.open(BytesIO(response.content))

    # pytesseract로 텍스트 추출
    img_array = np.array(img)
    text = pytesseract.image_to_string(img_array, config=config)

    if '원고' in text or '제공받아' in text or '수익' in text or '수수료' in text:
        return True
    
    return False

crawled_count = 0

def naver_crawler(html) :
    # 전역변수로 크롤링한 개수 누적
    global crawled_count
    idx = 0

    # 데이터를 저장할 dataframe
    post_df = pd.DataFrame(columns = ("Title", "Post URL",
                                      "Post" , "Post length", "Keyword(내돈내산)", 
                                      "Sponsered word"))

    
    soup = BeautifulSoup(html, 'html.parser')

    # 포스트 링크, 포스트 제목 가져오기
    posts = soup.find_all('div', {'class':'detail_box'})
    

    
    for post in posts[crawled_count: ] :
        title = post.find('a', {'class': 'title_link'}).text
        # 제목에 내돈내산 키워드 여부 검사
        if ('내돈' in title) or ('내돈내산' in title):
            keyword = 1
        else : 
            keyword = 0
        #링크 가져오기
        post_url = post.find('a', {'class': 'title_link'})['href']
        #requests 모듈로 post_url의 text 데이터를 가져오기
        post_text = requests.get(post_url).text
        #bs4로 html 문서를 파싱하여 포스트 안의 내용을 접근, 추출할 수 있게 변환
        post_html = BeautifulSoup(post_text, "html.parser")

        # 각 post는 iframe태그로 감싸져 있기 때문에 이를 제거하고 데이터 추출
        for main_frame in post_html.select("iframe#mainFrame"):
            frame_url = "https://blog.naver.com" + main_frame.get('src')
            post_text = requests.get(frame_url).text
            post_html = BeautifulSoup(post_text, 'html.parser')

            # 포스트 텍스트 크롤링
            post_content_text = ''
            for post_content in post_html.find_all('div', {'class' : 'se-main-container'}):
                post_content_text = post_content.get_text()
                # 개행문자 삭제
                post_content_text = post_content_text.replace("\n", "")
                post_content_text = post_content_text.replace("\t", "")
                
                #포스터 내돈내산 키워드 여부 검사
                if ('내돈내산' in post_content_text or '내돈' in post_content_text) and (keyword==0) :
                    keyword = 1 
                else :
                    keyword = 0
                
                # 협찬 문구 키워드 여부 검사 (이미지 문구 인식까지 디벨롭시켜야함)
                if '원고' in post_content_text or '제공받아' in post_content_text or '수익' in post_content_text or '수수료' in post_content_text:
                    sponsered = 1
                else :
                    sponsered = 0
                
                # # 협찬 이미지 문구 인식
                # post_content_imgs = post_html.find_all('a', {'class': '__se_sticker_link __se_link'})
                # if not post_content_imgs and sponsered == 0 :
                #     sponsered = 0
                # else:
                #     for post_content_img in post_content_imgs:
                #         image = post_content_img.find('img')
                #         image_url = image['src']
                #         extract_text(image_url)

                #         if extract_text(image_url) == True :
                #             sponsered = 1
                
                # 포스터 길이
                post_content_length = len(post_content_text)

            post_df.loc[idx] = [title, post_url, post_content_text, post_content_length, 
                                keyword, sponsered]
            idx += 1

    crawled_count += 30
    return post_df

def make_prediction(post_df) :

    X = post_df.drop(['Title', 'Post URL', 'Post'], axis=1)

    # 데이터 스케일링
    std = StandardScaler()
    X_scaled = std.fit_transform(X)

    predict = model.predict(X_scaled)

    return predict


@app.route("/naverblog", methods=['POST'])
def recieve_data() :
    data_from_js = request.get_json()
    html = data_from_js['source'] 
    post_df = naver_crawler(html)
    #print(post_df)

    #모델 예측
    prediction = make_prediction(post_df)
    prediction = prediction.tolist()
    print(prediction)
    return prediction

# 스크롤 했을 때 앤드포인트
@app.route("/naverblog/scroll", methods=['POST'])
def scroll_handler():
    data_from_js = request.get_json()
    html = data_from_js['source']
    post_df = naver_crawler(html)
    #print(post_df)
    
    #모델 예측
    prediction = make_prediction(post_df)
    prediction = prediction.tolist()
    print(prediction)
    return prediction

#HTTP health check
@app.route("/healthcheck", methods=['GET'])
def health_check():
    return jsonify(status="OK"), 200

if __name__ == '__main__':
    model = joblib.load('model/rf_model.pkl')
    app.run(host='0.0.0.0', port=8080, debug=True )
