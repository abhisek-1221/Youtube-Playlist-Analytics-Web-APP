from googleapiclient.discovery import build
import pandas as pd
import seaborn as sns
import re
from datetime import timedelta
import streamlit as st
from streamlit_lottie import st_lottie
from streamlit_lottie import st_lottie_spinner
import requests
import time
import matplotlib.pyplot as plt

st.set_option('deprecation.showPyplotGlobalUse', False)
#Setting up Page Configuration on Streamlit
st.set_page_config(
    page_title = 'Youtube Playlist Dashboard',
    page_icon = '📈',
    layout = 'wide'
)

#Creating two KPIs for 2 columns --- LHS Column(as kpi001) will show lottie anime and RHS Column will take Playlist ID input
kpi001, kpi002 = st.columns(2)

#Function to get lottie animation from url
def load_lottieurl(url:str):
    r=requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

#left column--for animation
with kpi001:
    welcome_anime = "https://assets5.lottiefiles.com/packages/lf20_M9p23l.json"
    st_lottie(load_lottieurl(welcome_anime), speed=1, loop=True, quality="medium", width=250,key="Hello")
#Right column for button and input
with kpi002:
    link=st.text_input("Enter Playlist Link")
    button = st.button("Show")

api_key = 'AIzaSyAzP1UE6cbhqL4NyLnV7jggkB_6e5uGuaE'
youtube = build('youtube', 'v3', developerKey=api_key) #Youtube API Version3

def extract_playlist_id(link):
    pattern = r"^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/|youtu\.be\/)?(?:playlist\?list=|)([\w-]{34})"
    # check if link is a valid YouTube playlist link
    match = re.match(pattern, link)
    if match:
        return match.group(1)
    else:
        return None

playlist_id = extract_playlist_id(link)


if button:
    def get_video_ids(youtube, playlist_id):
    
        request = youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId = playlist_id,
                    maxResults = 50) #maximum limit per request in a page is 50
        response = request.execute()
        
        video_ids = [] #creating an empty list where we will store video ids
        
        #storing video ids from the data recieved
        for i in range(len(response['items'])):
            video_ids.append(response['items'][i]['contentDetails']['videoId'])
            
        #A request can get maximum 50 results per page at a time..every page is assigned with a pagetoken.When there will be no more pages left then loop will break and we would have collected all videos ids from all pages(since we need multiple pagetokens incase of results exceeding 50)
        next_page_token = response.get('nextPageToken')
        more_pages = True
        
        while more_pages:
            if next_page_token is None:
                more_pages = False
            else:
                request = youtube.playlistItems().list(
                            part='contentDetails',
                            playlistId = playlist_id,
                            maxResults = 50,
                            pageToken = next_page_token)
                response = request.execute()
        
                for i in range(len(response['items'])):
                    video_ids.append(response['items'][i]['contentDetails']['videoId'])
                
                next_page_token = response.get('nextPageToken')
            #if newpagetoken then loop continues(since more pages=true)if nextpagetoken is none that means no furtherpage exists and we have collected all video ids..thus more pages=false and loop will terminate its execution
        return video_ids


    video_ids = get_video_ids(youtube, playlist_id) #calling the above function to get the video_ids
    total_vid=len(video_ids) #to find the total number of videos in the playlist

    #Function to get all video details
    def get_video_details(youtube, video_ids):
        all_video_stats = [] #creating an empty list to store all video stats for each video of playlist via their video_ids
        
        #since maximum of 50 results per request but we need to get stats of all videos of playlist(via their video ids). By iterating the loop from 0 till the total numbers of videos by taking 50 ids at a time
        for i in range(0, len(video_ids), 50):  
            request = youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(video_ids[i:i+50]))  #joining vid_id 50 at a time i.e 0-50 then 50-100 etc
            response = request.execute()
            
            #creating a dictionary to store all obtained data before converting them to a DataFrame
            for video in response['items']:
                video_stats = dict(Title = video['snippet']['title'],
                                Published_date = video['snippet']['publishedAt'],
                                Views = video['statistics']['viewCount'],
                                Likes = video['statistics']['likeCount'],
                                Duration = video['contentDetails']['duration'],
                                Comments = video['statistics']['commentCount']
                                )
                all_video_stats.append(video_stats)
        
        return all_video_stats

    video_details = get_video_details(youtube, video_ids) #calling the above function where we get video details
    video_data = pd.DataFrame(video_details) #created a dataframe of all video details we had collected
    video_data['Published_date'] = pd.to_datetime(video_data['Published_date']).dt.date
    video_data['Views'] = pd.to_numeric(video_data['Views'])
    video_data['Likes'] = pd.to_numeric(video_data['Likes'])
    video_data['Comments'] = pd.to_numeric(video_data['Comments'])

    top_videos = video_data.sort_values(by='Views', ascending=False).head(10) #sorting Most viewed videos
    video_data['Month'] = pd.to_datetime(video_data['Published_date']).dt.strftime('%b')
    videos_per_month = video_data.groupby('Month', as_index=False).size()
    sort_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    videos_per_month.index = pd.CategoricalIndex(videos_per_month['Month'], categories=sort_order, ordered=True)
    videos_per_month = videos_per_month.sort_index() 

    #below is regular expression formats where we get duration from the Duration output we got in format PT4H12M7S = playtime 14 hours 12 mins ad 7 seconds
    minutes_pattern=re.compile(r'(\d+)M')
    seconds_pattern=re.compile(r'(\d+)S') # \d+)S means the digit that is present before S
    hours_pattern=re.compile(r'(\d+)H')

    #storing all values of Duration Column in a new variable named dur
    dur=video_data.loc[:,"Duration"]  #.loc used to access location
    
    #creating a variable total seconds set at 0 where we will add durations of all videos after converting them into seconds (one video at a time in a loop below)- we will later use this second to convert this time to get durations for different playback speed 
    total_seconds=0
    for vd in range(0,len(dur)):  #we access each duration we stored in variable dur from the above dataframe
        fin_dur=(dur[vd])   #here we store one duration in a variable named final duration and then convert them to get Hr.min.sec from PTXHXMXS pattern
        hours = hours_pattern.search(fin_dur)
        minutes = minutes_pattern.search(fin_dur)
        seconds = seconds_pattern.search(fin_dur)
        
        hours = int(hours.group(1)) if hours else 0
        minutes = int(minutes.group(1)) if minutes else 0
        seconds = int(seconds.group(1)) if seconds else 0
        
        video_seconds = timedelta(
            hours=hours,
            minutes=minutes,
            seconds=seconds
            ).total_seconds() #here we used timedelta function to convert all hrs,min,sec to video seconds = duration of each video in seconds
        total_seconds += video_seconds  #we add duration of each video seconds to total seconds = duration of all videos in the playlist to get duration of total playlist in terms of seconds

    minutes, seconds = divmod(total_seconds, 60)  #divmod function used here..basically--- min=totalsec//60(quotient) , seconds=totalsec%60(remainder)
    hours, minutes = divmod(minutes, 60)

    total_seconds = int(total_seconds)
    total_seconds2 = int(total_seconds//1.25)  #to get duration of playlist in seconds at 1.25x speed
    total_seconds3 = int(total_seconds//1.5)  #to get duration of playlist in seconds at 1.5x speed
    total_seconds4 = int(total_seconds//1.75) #to get duration of playlist in seconds at 1.75x speed
    total_seconds5 = int(total_seconds//2) #to get duration of playlist in seconds at 2x speed

    #below we converted total seconds to hours.minutes.seconds for each playback speed 
    #the end suffix 2 is for playblack speed 1.25x
    #3 for 1.5x speed
    #4 for 1.75x speed
    #5 for 2x speed
    minutes2, seconds2 = divmod(total_seconds2, 60)
    hours2, minutes2 = divmod(minutes2, 60)

    minutes3, seconds3 = divmod(total_seconds3, 60)
    hours3, minutes3 = divmod(minutes3, 60)

    minutes4, seconds4 = divmod(total_seconds4, 60)
    hours4, minutes4 = divmod(minutes4, 60)

    minutes5, seconds5 = divmod(total_seconds5, 60)
    hours5, minutes5 = divmod(minutes5, 60)

    #here we added lottie animation for loadind animation after clicking button (show)
    load_anim  = "https://assets1.lottiefiles.com/packages/lf20_t9gkkhz4.json"  #load animation url
    with st_lottie_spinner(load_lottieurl(load_anim), key="load",width=670):
        time.sleep(3) #basically the load animation stays for 3 seconds 

    st.markdown("## Playlist Details") 
    kpi1, kpi2 = st.columns(2) #created 2 columns where in LHS for totalvideos and RHS for Total Duration of playlist  
    with kpi1:
        st.markdown('''### Total Videos''')
        st.markdown(f"<h1 style='text-align: left; color: red;'>{total_vid}</h1>", unsafe_allow_html=True)

    with kpi2:
        st.markdown('''### Total Duration of Playlist''')
        st.markdown(f"<h3 style='text-align: centre; color: red;'>{int(hours)}Hr {int(minutes)}Min {int(seconds)}Sec</h3>", unsafe_allow_html=True)

    kpi01, kpi02, kpi03, kpi04 = st.columns(4) #4 columns for different playback speed duration

    with kpi01:
        st.markdown('''### Duration at 1.25x speed''')
        st.markdown(f"<h3 style='text-align: left; color: yellow;'>{hours2}Hr {minutes2}Min {seconds2}Sec</h3>", unsafe_allow_html=True)

    with kpi02:
        st.markdown('''### Duration at 1.5x speed''')
        st.markdown(f"<h3 style='text-align: left; color: yellow;'>{hours3}Hr {minutes3}Min {seconds3}Sec</h3>", unsafe_allow_html=True)

    with kpi03:
        st.markdown('''### Duration at 1.75x speed''')
        st.markdown(f"<h3 style='text-align: left; color: yellow;'>{hours4}Hr {minutes4}Min {seconds4}Sec</h3>", unsafe_allow_html=True)

    with kpi04:
        st.markdown('''### Duration at 2x speed''')
        st.markdown(f"<h3 style='text-align: left; color: yellow;'>{hours5}Hr {minutes5}Min {seconds5}Sec</h3>", unsafe_allow_html=True)

    
    chart_anim  = "https://assets2.lottiefiles.com/packages/lf20_ATo2OG.json"
    display_chart = load_lottieurl(chart_anim)
    with st_lottie_spinner(display_chart, key="Charts",width=400): #chart loading animation
        time.sleep(5) #loading animation last for 5 seconds 
        chart1, chart2 = st.columns(2) 
        with chart1:
            fig=plt.figure()
            plt.title("Top 10 Videos by Views")
            sns.barplot(x='Views', y='Title', data=top_videos)
            st.pyplot(fig)
        with chart2:
            fig = plt.figure()
            plt.title("Videos Uploaded per Month")
            sns.barplot(x='Month', y='size', data=videos_per_month) #bar graph shows number of videos uploaded per month
            st.pyplot(fig)

        chart3, chart4 = st.columns(2)
        with chart3:
            plt.scatter(video_data['Views'],video_data['Likes'], c=video_data['Comments'], cmap='summer',
                edgecolors='black',linewidths=1, alpha=0.75)
            plt.title("Views to Like Distribution")
            cbar = plt.colorbar()
            cbar.set_label('Comment Distribution')
            plt.xlabel('Views')
            plt.ylabel('Total Likes')
            plt.tight_layout()
            st.pyplot()
        with chart4:
            plt.scatter(video_data['Comments'],video_data['Likes'], c=video_data['Views'], cmap='summer',
                edgecolors='black',linewidths=1, alpha=0.75)
            plt.title("Comments to Like Distribution")
            cbar = plt.colorbar()
            cbar.set_label('Views Distribution')
            plt.xscale('log')
            plt.yscale('log')
            plt.xlabel('Comments')
            plt.ylabel('Total Likes')
            plt.tight_layout()
            st.pyplot()
        
        st.dataframe(video_data)


