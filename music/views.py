from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Song, UserBehavior, SongSimilarity
from .forms import UserPreferenceForm
from django.http import JsonResponse
import requests
import json
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
import openai  # 需要安装：pip install openai
import logging  # 添加这行

# 配置logger
logger = logging.getLogger(__name__)

def get_sample_songs():
    """获取音乐列表"""
    try:
        # QQ音乐热歌榜API
        api_url = "https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg"
        params = {
            'topid': '26',  # 热歌榜
            'format': 'json',
            'inCharset': 'utf-8',
            'outCharset': 'utf-8'
        }
        headers = {
            'Referer': 'https://y.qq.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            songs = []
            for song_data in data.get('songlist', [])[:18]:  # 获取前18首歌
                song_info = song_data.get('data', {})
                mid = song_info.get('songmid', '')
                
                # 获取歌词
                lyrics = ""
                try:
                    lyrics_url = f"https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
                    lyrics_params = {
                        'songmid': mid,
                        'format': 'json',
                        'nobase64': 1
                    }
                    lyrics_headers = {
                        'Referer': 'https://y.qq.com',
                        'User-Agent': 'Mozilla/5.0'
                    }
                    lyrics_response = requests.get(lyrics_url, params=lyrics_params, headers=lyrics_headers)
                    if lyrics_response.status_code == 200:
                        lyrics_data = lyrics_response.json()
                        lyrics = lyrics_data.get('lyric', '')
                except Exception as e:
                    print(f"获取歌词失败: {e}")
                
                songs.append({
                    'title': song_info.get('songname', ''),
                    'artist': song_info.get('singer', [{}])[0].get('name', ''),
                    'audio_url': f'https://dl.stream.qqmusic.qq.com/C400{mid}.m4a?guid=1234567890&vkey=123456&uin=0&fromtag=38',
                    'cover_url': f'https://y.gtimg.cn/music/photo_new/T002R300x300M000{song_info.get("albummid")}.jpg',
                    'lyrics': lyrics
                })
            return songs
    except Exception as e:
        print(f"Error: {e}")
        # 备用音乐列表
        return [
            {
                'title': '起风了',
                'artist': '买辣椒也用券',
                'audio_url': 'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701923.mp3',
                'cover_url': 'https://cdnmusic.migu.cn/picture/2019/1031/0254/ASd6c2d576e8894916a442d1b6a5f881c7.jpg',
            },
            {
                'title': '我记得',
                'artist': '赵雷',
                'audio_url': 'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701937.mp3',
                'cover_url': 'https://cdnmusic.migu.cn/picture/2019/1031/0254/AS8e8f9b8dd0ab4d10a907847168e2bda0.jpg',
            },
            {
                'title': '光年之外',
                'artist': '邓紫棋',
                'audio_url': 'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701943.mp3',
                'cover_url': 'https://cdnmusic.migu.cn/picture/2019/1031/0842/AM8d1f156607b04d65b67f06eaad68d2a3.jpg',
            }
        ]

@login_required
def index(request):
    """显示用户收藏的音乐"""
    # 获取用户收藏的歌曲
    behaviors = UserBehavior.objects.filter(
        user=request.user, 
        favorited=True
    ).select_related('song')
    
    # 转换为列表格式
    songs = [{
        'title': behavior.song.title,
        'artist': behavior.song.artist,
        'audio_url': behavior.song.audio_url,
        'cover_url': behavior.song.cover_url,
        'is_favorited': True,
        'id': behavior.song.id
    } for behavior in behaviors]
    
    # 分页处理
    paginator = Paginator(songs, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'music/index.html', {
        'page_obj': page_obj,
        'is_paginated': True,
        'paginator': paginator
    })

def get_random_recommendations(size=12):
    """获取随机推荐歌曲"""
    try:
        api_url = "https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg"
        params = {
            'topid': '26',
            'format': 'json',
            'inCharset': 'utf-8',
            'outCharset': 'utf-8'
        }
        headers = {
            'Referer': 'https://y.qq.com',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(api_url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            songs = []
            for song_data in data.get('songlist', []):
                song_info = song_data.get('data', {})
                mid = song_info.get('songmid', '')
                songs.append({
                    'title': song_info.get('songname', ''),
                    'artist': song_info.get('singer', [{}])[0].get('name', ''),
                    'audio_url': f'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701923.mp3',
                    'cover_url': f'https://y.gtimg.cn/music/photo_new/T002R300x300M000{song_info.get("albummid")}.jpg',
                    'reason': '随机推荐'
                })
            import random
            random.shuffle(songs)
            return songs[:size]
    except Exception as e:
        print(f"获取随机推荐失败: {str(e)}")
        return get_sample_songs()[:size]

@login_required
def get_recommendations_view(request):
    """获取推荐列表"""
    refresh = request.GET.get('refresh', False)
    search_query = request.GET.get('search', '').strip()
    search_mode = request.GET.get('search_mode', 'normal')
    
    # 如果有搜索查询
    if search_query:
        try:
            # 如果是自然语言搜索模式
            if search_mode == 'natural':
                try:
                    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                    
                    # 构建提示词
                    prompt = f"""
                    请将以下口语化的音乐需求转换为搜索关键词：
                    "{search_query}"
                    只需要返回关键词，用空格分隔，不要其他内容。
                    """
                    
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "你是一个音乐搜索助手，帮助用户将自然语言转换为搜索关键词。"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7,
                            max_tokens=50
                        )
                        
                        # 获取生成的关键词
                        keywords = response.choices[0].message.content.strip()
                        search_query = keywords  # 使用转换后的关键词进行搜索
                        
                    except Exception as e:
                        logger.error(f"OpenAI API调用失败: {str(e)}")
                        # 如果API调用失败，继续使用原始查询
                except Exception as e:
                    logger.error(f"OpenAI客户端初始化失败: {str(e)}")
            
            # 从本地数据库搜索
            local_songs = Song.objects.filter(
                Q(lyrics__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(artist__icontains=search_query)
            )[:12]
            
            if local_songs.exists():
                search_results = []
                for song in local_songs:
                    song_item = {
                        'title': song.title,
                        'artist': song.artist,
                        'audio_url': song.audio_url,
                        'cover_url': song.cover_url,
                        'reason': f'匹配歌词/标题: {search_query}'
                    }
                    
                    # 检查是否已被收藏
                    try:
                        behavior = UserBehavior.objects.get(
                            user=request.user,
                            song=song
                        )
                        song_item['is_favorited'] = behavior.favorited
                    except UserBehavior.DoesNotExist:
                        song_item['is_favorited'] = False
                    
                    search_results.append(song_item)
                    
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'recommendations': search_results})
                
                return render(request, 'music/recommendation.html', {
                    'recommendations': search_results,
                    'search_query': search_query,
                    'search_mode': search_mode
                })
            
            # 如果本地没有找到，则尝试从QQ音乐API搜索
            api_url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
            params = {
                'w': search_query,
                'format': 'json',
                'inCharset': 'utf-8',
                'outCharset': 'utf-8',
                'platform': 'yqq',
                'needNewCode': 0,
                'p': 1,
                'n': 12
            }
            headers = {
                'Referer': 'https://y.qq.com',
                'User-Agent': 'Mozilla/5.0'
            }
            
            response = requests.get(api_url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                search_results = []
                
                for song_data in data.get('data', {}).get('song', {}).get('list', []):
                    mid = song_data.get('songmid', '')
                    albummid = song_data.get('albummid', '')
                    
                    song_item = {
                        'title': song_data.get('songname', ''),
                        'artist': song_data.get('singer', [{}])[0].get('name', ''),
                        'audio_url': f'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701923.mp3',
                        'cover_url': f'https://y.gtimg.cn/music/photo_new/T002R300x300M000{albummid}.jpg',
                        'reason': f'搜索结果: {search_query}'
                    }
                    
                    # 检查是否已被收藏
                    try:
                        behavior = UserBehavior.objects.get(
                            user=request.user,
                            song__title=song_item['title'],
                            song__artist=song_item['artist']
                        )
                        song_item['is_favorited'] = behavior.favorited
                    except UserBehavior.DoesNotExist:
                        song_item['is_favorited'] = False
                    
                    search_results.append(song_item)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'recommendations': search_results})
                
                return render(request, 'music/recommendation.html', {
                    'recommendations': search_results,
                    'search_query': search_query,
                    'search_mode': search_mode
                })
                
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            # 如果搜索失败，回退到本地搜索
            pass
    
    # 如果没有搜索查询或API搜索失败，使用原有的推荐逻辑
    behaviors = UserBehavior.objects.filter(
        user=request.user, 
        favorited=True
    ).select_related('song')
    
    if refresh == 'true' or 'current_recommendations' not in request.session:
        if behaviors.exists():
            similar_songs = get_song_recommendations(request.user)[:4]
            random_songs = get_random_recommendations(8)
            all_songs = similar_songs + random_songs
            import random
            random.shuffle(all_songs)
            recommendations = all_songs[:12]
        else:
            recommendations = get_random_recommendations(12)
        
        # 检查每首歌是否已被收藏
        for song in recommendations:
            try:
                behavior = UserBehavior.objects.get(
                    user=request.user,
                    song__title=song['title'],
                    song__artist=song['artist']
                )
                song['is_favorited'] = behavior.favorited
            except UserBehavior.DoesNotExist:
                song['is_favorited'] = False
        
        request.session['current_recommendations'] = [dict(r) for r in recommendations]
    else:
        recommendations = request.session.get('current_recommendations', [])
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'recommendations': recommendations
        })
    
    return render(request, 'music/recommendation.html', {
        'recommendations': recommendations,
        'search_query': search_query,
        'search_mode': search_mode
    })

@login_required
def get_music_api(request):
    songs = get_sample_songs()
    return JsonResponse({'recommendations': songs})

@login_required
def rate_song(request, song_id):
    if request.method == 'POST':
        song = get_object_or_404(Song, id=song_id)
        form = UserPreferenceForm(request.POST)
        if form.is_valid():
            behavior, created = UserBehavior.objects.get_or_create(
                user=request.user,
                song=song,
                defaults={
                    'play_count': 1,
                    'favorited': True
                }
            )
            messages.success(request, '评价已更新！')
        else:
            messages.error(request, '评价提交失败，请重试。')
    return redirect('music:index') 

@login_required
def toggle_favorite(request):
    """处理收藏/取消收藏"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title')
            artist = data.get('artist')
            audio_url = data.get('audio_url')
            cover_url = data.get('cover_url')
            
            # 获取或创建歌曲记录
            song, _ = Song.objects.get_or_create(
                title=title,
                artist=artist,
                defaults={
                    'audio_url': audio_url,
                    'cover_url': cover_url
                }
            )
            
            # 更新用户行为
            behavior, created = UserBehavior.objects.get_or_create(
                user=request.user,
                song=song,
                defaults={'favorited': True}
            )
            
            if not created:
                behavior.favorited = not behavior.favorited
                behavior.save()
            
            return JsonResponse({
                'status': 'success',
                'favorited': behavior.favorited
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': '仅支持POST请求'
    }, status=405)

@login_required
def record_play(request, song_id):
    """记录播放行为"""
    try:
        song = Song.objects.get(id=song_id)
        behavior, _ = UserBehavior.objects.get_or_create(
            user=request.user,
            song=song
        )
        behavior.play_count += 1
        behavior.save()
        
        return JsonResponse({'status': 'success'})
    except Song.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '歌曲不存在'
        }, status=404)

def get_song_recommendations(user):
    """基于用户收藏的歌曲风格的推荐"""
    behaviors = UserBehavior.objects.filter(
        user=user, 
        favorited=True
    ).select_related('song')
    
    # 如果用户没有收藏记录，返回12首随机推荐
    if not behaviors.exists():
        random_songs = get_random_recommendations(12)
        for song in random_songs:
            song['reason'] = '随机推荐'
        return random_songs
    
    # 获取所有收藏的歌曲标题，用于后续过滤已收藏的歌曲
    favorite_titles = [b.song.title for b in behaviors]
    
    # 从QQ音乐API获取推荐歌曲
    recommendations = []
    try:
        api_url = "https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg"
        params = {
            'topid': '26',
            'format': 'json',
            'inCharset': 'utf-8',
            'outCharset': 'utf-8'
        }
        headers = {
            'Referer': 'https://y.qq.com',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(api_url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            
            # 收集所有可能的推荐歌曲
            style_based_songs = []  # 基于风格的推荐
            
            # 定义一些简单的风格关键词匹配规则
            style_keywords = {
                '摇滚': ['摇滚', '电吉他', 'rock', 'Rock'],
                '民谣': ['民谣', '吉他', '木吉他', 'folk'],
                '流行': ['流行', 'pop', 'Pop', '情歌'],
                '电子': ['电子', 'EDM', 'dance', 'Dance'],
                '嘻哈': ['说唱', '饶舌', 'rap', 'Rap', '嘻哈'],
                '爵士': ['爵士', 'jazz', 'Jazz', '蓝调'],
                '古风': ['古风', '国风', '古典'],
            }
            
            # 获取用户收藏歌曲的风格倾向
            user_style_preferences = set()
            for behavior in behaviors:
                song_title = behavior.song.title
                for style, keywords in style_keywords.items():
                    if any(keyword in song_title for keyword in keywords):
                        user_style_preferences.add(style)
            
            # 如果没有识别出风格偏好，添加"流行"作为默认风格
            if not user_style_preferences:
                user_style_preferences.add('流行')
            
            for song_data in data.get('songlist', []):
                song_info = song_data.get('data', {})
                current_title = song_info.get('songname', '')
                
                # 跳过已收藏的歌曲
                if current_title in favorite_titles:
                    continue
                
                current_artist = song_info.get('singer', [{}])[0].get('name', '')
                mid = song_info.get('songmid', '')
                
                # 检查歌曲风格
                matched_style = None
                for style, keywords in style_keywords.items():
                    if any(keyword in current_title for keyword in keywords):
                        matched_style = style
                        break
                
                # 如果歌曲风格匹配用户偏好
                if matched_style and matched_style in user_style_preferences:
                    song_item = {
                        'title': current_title,
                        'artist': current_artist,
                        'audio_url': f'https://freetyst.nf.migu.cn/public/product9th/product45/2022/07/2614/2009年06月26日博尔普斯/标清高清/MP3_128_16_Stero/60054701923.mp3',
                        'cover_url': f'https://y.gtimg.cn/music/photo_new/T002R300x300M000{song_info.get("albummid")}.jpg',
                        'reason': f'因为您喜欢{matched_style}风格的音乐'
                    }
                    style_based_songs.append(song_item)
            
            # 随机选择推荐歌曲
            import random
            recommendations = []
            
            # 获取4首基于风格的推荐
            if style_based_songs:
                random.shuffle(style_based_songs)
                recommendations.extend(style_based_songs[:4])
            
            # 如果基于风格的推荐不足4首，补充随机推荐凑够4首
            if len(recommendations) < 4:
                remaining_count = 4 - len(recommendations)
                random_songs = get_random_recommendations(remaining_count)
                for song in random_songs:
                    song['reason'] = '随机推荐'
                recommendations.extend(random_songs)
            
            # 再添加8首随机推荐
            random_songs = get_random_recommendations(8)
            for song in random_songs:
                song['reason'] = '随机推荐'
            recommendations.extend(random_songs)
            
    except Exception as e:
        print(f"推荐获取失败: {str(e)}")
        # 如果获取推荐失败，返回12首随机推荐
        random_songs = get_random_recommendations(12)
        for song in random_songs:
            song['reason'] = '随机推荐'
        return random_songs
    
    return recommendations 