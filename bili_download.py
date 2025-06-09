import requests
import time
import urllib.request
import re
import os
import sys
from moviepy import VideoFileClip, AudioFileClip
import subprocess

class BilibiliDownloader:
    """B站视频下载器"""
    
    QUALITY_MAP = {
        120: "超清4K (需要大会员)",
        116: "高清1080P60 (需要大会员)",
        112: "高清1080P+ (需要大会员)",
        80: "高清1080P",
        74: "高清720P60 (需要大会员)",
        64: "高清720P",
        32: "清晰480P",
        16: "流畅360P"
    }
    
    def __init__(self, sessdata="your_sessdata_here"):
        self.sessdata = sessdata
        self.download_dir = os.path.join(sys.path[0], 'bili_download') # 下载存放文件夹
        self.start_time = None
        
    def _get_headers(self, host="api.bilibili.com", referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Host': host
        }
        
        if self.sessdata:
            headers['Cookie'] = f'SESSDATA={self.sessdata}'
            
        if referer:
            headers['Referer'] = referer
            
        return headers
    
    def _parse_input(self, input_str):
        aid = bvid = None
        
        if 'bilibili.com' in input_str:
            if bv_match := re.search(r'/BV([a-zA-Z0-9]+)/*', input_str):
                bvid = bv_match.group(1)
            elif av_match := re.search(r'/av(\d+)/*', input_str):
                aid = av_match.group(1)
        elif input_str.isdigit():
            aid = input_str
        elif re.match(r'BV[a-zA-Z0-9]+', input_str):
            bvid = input_str
        
        base_url = 'https://api.bilibili.com/x/web-interface/view?'
        api_url = base_url + (f'bvid={bvid}' if bvid else f'aid={aid}')
            
        return aid, bvid, api_url
    
    def _get_video_info(self, api_url):
        try:
            response = requests.get(api_url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 0:
                raise Exception(f"API返回错误: {data.get('message', '未知错误')}")
                
            return data['data']
        except requests.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")
    
    def _get_play_list(self, aid, bvid, cid, quality):
        # 尝试获取DASH格式
        dash_urls = self._get_dash_play_list(aid, bvid, cid, quality)
        if dash_urls:
            return dash_urls
        
        # 回退到传统API
        return self._get_legacy_play_list(aid, bvid, cid, quality)
    
    def _get_dash_play_list(self, aid, bvid, cid, quality):
        url_api = f'https://api.bilibili.com/x/player/wbi/playurl?cid={cid}&{"bvid="+bvid if bvid else "avid="+aid}&qn={quality}&fourk=1&fnver=0&fnval=4048'
        
        try:
            headers = self._get_headers()
            headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://www.bilibili.com',
                'DNT': '1',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            })
            
            response = requests.get(url_api, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 0:
                return None
            
            play_data = data.get('data', {})
            
            if 'dash' in play_data:
                return self._parse_dash_data(play_data['dash'])
            return None
                
        except Exception:
            return None
    
    def _parse_dash_data(self, dash_data):
        video_urls = []
        audio_urls = []
        
        # 解析视频流
        if videos := dash_data.get('video', []):
            best_video = max(videos, key=lambda x: x.get('bandwidth', 0))
            if video_url := best_video.get('baseUrl') or best_video.get('base_url'):
                video_urls.append({
                    'url': video_url,
                    'backup_urls': best_video.get('backupUrl', []) or best_video.get('backup_url', []),
                    'type': 'dash_video',
                    'quality': best_video.get('id', 0),
                })
        
        # 解析音频流
        if audios := dash_data.get('audio', []):
            best_audio = max(audios, key=lambda x: x.get('bandwidth', 0))
            if audio_url := best_audio.get('baseUrl') or best_audio.get('base_url'):
                audio_urls.append({
                    'url': audio_url,
                    'backup_urls': best_audio.get('backupUrl', []) or best_audio.get('backup_url', []),
                    'type': 'dash_audio',
                    'quality': best_audio.get('id', 0),
                })
        
        return video_urls + audio_urls
    
    def _get_legacy_play_list(self, aid, bvid, cid, quality):
        url_api = f'https://api.bilibili.com/x/player/playurl?cid={cid}&{"bvid="+bvid if bvid else "avid="+aid}&qn={quality}'
        
        try:
            response = requests.get(url_api, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 0:
                raise Exception(f"获取下载链接失败: {data.get('message', '未知错误')}")
            
            if 'data' not in data or 'durl' not in data['data']:
                raise Exception("返回数据格式错误")
            
            # 转换为统一格式
            return [{
                'url': item['url'],
                'backup_urls': item.get('backup_url', []),
                'type': 'video',
                'quality': quality,
            } for item in data['data']['durl']]
            
        except requests.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")
    
    def _format_size(self, bytes_size):
        
        try:
            bytes_size = float(bytes_size)
            if (gb := bytes_size / (1024**3)) >= 1:
                return f"{gb:.2f}GB"
            elif (mb := bytes_size / (1024**2)) >= 1:
                return f"{mb:.2f}MB"
            elif (kb := bytes_size / 1024) >= 1:
                return f"{kb:.2f}KB"
            return f"{bytes_size}B"
        except:
            return "未知大小"
    
    def _progress_callback(self, blocknum, blocksize, totalsize):
        """下载进度回调函数"""
        if self.start_time is None:
            self.start_time = time.time()
            return
            
        recv_size = blocknum * blocksize
        percent = recv_size / totalsize
        
        # 每下载1%更新一次进度
        if percent == 1.0 or blocknum % max(1, int(totalsize / blocksize / 100)) == 0:
            elapsed = time.time() - self.start_time
            speed = recv_size / elapsed if elapsed > 0 else 0
            speed_str = f"速度: {self._format_size(speed)}/s"
            percent_str = f"{percent * 100:.1f}%"
            
            sys.stdout.write(f"\r{percent_str.ljust(8)} {speed_str.ljust(20)}")
            sys.stdout.flush()
    
    def _sanitize_filename(self, filename):
        """清理文件名中的非法字符，保留所有合法Unicode字符"""
        if not filename or not isinstance(filename, str):
            return "未命名视频"
        
        # 只移除Windows不允许的字符
        illegal_chars = r'[\\/*?:"<>|\n\r\t]'
        sanitized = re.sub(illegal_chars, '', filename)
        
        # 确保名称不超过最大长度（避免路径问题）
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length-3] + '...'
        
        # 处理可能出现的为空情况
        return sanitized.strip() or "未命名视频"
    
    def _download_media(self, media_list, title, referer_url, page):
        """下载媒体文件（视频/音频）"""
        print(f'\n[正在下载P{page}段视频]: {title}')
        
        # 创建下载目录
        video_path = os.path.join(self.download_dir, title)
        os.makedirs(video_path, exist_ok=True)
        
        # 设置下载器
        opener = urllib.request.build_opener()
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            ('Referer', referer_url),
            ('Origin', 'https://www.bilibili.com'),
        ]
        urllib.request.install_opener(opener)
        
        downloaded_files = []
        self.start_time = time.time()
        
        # 下载所有媒体文件
        for media_info in media_list:
            media_type = media_info['type']
            filename = f'{title}-{media_type}.m4s'
            filepath = os.path.join(video_path, filename)
            
            # 尝试主URL和备用URL
            for url_index, url in enumerate([media_info['url']] + media_info.get('backup_urls', [])):
                try:
                    print(f"\n下载{media_type.replace('_', ' ')}...")
                    urllib.request.urlretrieve(
                        url=url,
                        filename=filepath,
                        reporthook=self._progress_callback
                    )
                    print(f"\n{media_type.replace('_', ' ')} 下载完成")
                    downloaded_files.append((filepath, media_type))
                    break
                except Exception as e:
                    if url_index < len(media_info.get('backup_urls', [])):
                        print(f"下载失败: {str(e)}，尝试备用URL...")
                    else:
                        print(f"所有URL都下载失败: {str(e)}")
                        raise
        
        return downloaded_files
    
    def _merge_media_files(self, downloaded_files, title):
        """合并媒体文件"""
        video_path = os.path.join(self.download_dir, title)
        video_file = audio_file = None
        
        # 分离视频和音频文件
        for filepath, media_type in downloaded_files:
            if media_type == 'dash_video':
                video_file = filepath
            elif media_type == 'dash_audio':
                audio_file = filepath
            elif media_type == 'video':
                # 传统视频文件直接重命名
                os.rename(filepath, os.path.join(video_path, f'{title}.mp4'))
                return
        
        # 合并DASH视频和音频
        if video_file and audio_file:
            output_path = os.path.join(video_path, f'{title}.mp4')
            self._merge_with_ffmpeg(video_file, audio_file, output_path)
            
            # 清理临时文件
            try:
                os.remove(video_file)
                os.remove(audio_file)
            except:
                pass
        elif video_file:
            os.rename(video_file, os.path.join(video_path, f'{title}.mp4'))
        elif audio_file:
            os.rename(audio_file, os.path.join(video_path, f'{title}.m4a'))
    
    def _merge_with_ffmpeg(self, video_file, audio_file, output_path):
        """使用ffmpeg合并音视频"""
        try:
            # 尝试使用ffmpeg
            subprocess.run(
                ['ffmpeg', '-i', video_file, '-i', audio_file, '-c', 'copy', '-y', output_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            print("音视频合并完成")
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 回退到moviepy
            print("ffmpeg不可用，尝试使用moviepy合并...")
            self._merge_with_moviepy(video_file, audio_file, output_path)
    
    def _merge_with_moviepy(self, video_file, audio_file, output_path):
        """使用moviepy合并音视频"""
        try:
            video_clip = VideoFileClip(video_file)
            audio_clip = AudioFileClip(audio_file)
            final_clip = video_clip.set_audio(audio_clip)
            final_clip.write_videofile(
                output_path, 
                codec='libx264', 
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            video_clip.close()
            audio_clip.close()
            final_clip.close()
            print("音视频合并完成")
        except Exception as e:
            raise Exception(f"moviepy合并失败: {str(e)}")
    
    def download(self, input_str, quality=80, target_page=None):
        """
        下载视频
        
        Args:
            input_str: 视频链接、av号或BV号
            quality: 视频质量
            target_page: 指定下载的分P页面，None表示下载全部
        """
        try:
            # 解析输入
            aid, bvid, api_url = self._parse_input(input_str)
            
            # 获取视频信息
            video_info = self._get_video_info(api_url)
            title = self._sanitize_filename(video_info['title'])
            print(f"\n视频标题: {title}")
            print(f"UP主: {video_info.get('owner', {}).get('name', '未知')}")
            
            # 确定要下载的页面
            pages = video_info['pages']
            if target_page is not None and 1 <= target_page <= len(pages):
                pages_to_download = [pages[target_page - 1]]
                print(f"将下载指定分P: P{target_page}")
            else:
                pages_to_download = pages
                print(f"将下载全部分P (共{len(pages)}个)")
            
            # 下载每个分P
            for page_info in pages_to_download:
                cid = str(page_info['cid'])
                
                # 判断分P标题是否为空
                if page_info['part']:
                    part_title = self._sanitize_filename(page_info['part'])
                else:
                    part_title = self._sanitize_filename(title)

                page = str(page_info['page'])
                
                # 使用页码作为最后保障
                if not part_title:
                    part_title = f"分P{page}"
                
                # 调试日志：实际验证标题内容
                print(f'原始分P标题: {page_info["part"]}')
                print(f'处理后标题: {part_title}')
                
                # 构建referer URL
                referer_url = f"https://www.bilibili.com/video/{bvid and 'BV'+bvid or 'av'+aid}/?p={page}"
                
                # 获取下载链接
                media_list = self._get_play_list(aid, bvid, cid, quality)
                if not media_list:
                    print(f"获取下载链接失败，跳过P{page}")
                    continue
                
                # 下载并合并媒体文件
                downloaded_files = self._download_media(media_list, part_title, referer_url, page)
                self._merge_media_files(downloaded_files, part_title)
                print(f'[下载完成] P{page} - {part_title}')
            
            # 下载完成后打开目录
            if sys.platform == 'win32':
                os.startfile(self.download_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.download_dir])
            else:
                subprocess.Popen(['xdg-open', self.download_dir])
                    
        except Exception as e:
            print(f"下载失败: {str(e)}")


def main():
    """主程序入口"""
    print('-' * 30 + 'B站视频下载助手' + '-' * 30)
    
    # 获取用户输入
    video_input = input('请输入您要下载的B站av号、BV号或者视频链接地址: ')
    
    # 创建下载器实例
    downloader = BilibiliDownloader()
    
    # 尝试解析视频信息
    target_page = None
    try:
        aid, bvid, api_url = downloader._parse_input(video_input)
        video_info = downloader._get_video_info(api_url)
        pages = video_info['pages']
        
        # 检查URL中的分P参数
        if p_match := re.search(r'[\?&]p=(\d+)', video_input):
            p_num = int(p_match.group(1))
            if 1 <= p_num <= len(pages):
                target_page = p_num
                print(f"检测到链接中指定的分P: P{p_num}")
        
        # 多分P选择
        if not target_page and len(pages) > 1:
            print(f"\n该视频共有 {len(pages)} 个分P:")
            for i, page in enumerate(pages[:5], 1):
                print(f"  P{page['page']}: {page['part'][:30]}{'...' if len(page['part']) > 30 else ''}")
            
            if len(pages) > 5:
                print(f"  ... 还有 {len(pages) - 5} 个分P")
            
            choice = input("\n请选择:\n1. 下载全部分P\n2. 下载指定分P\n> ").strip()
            if choice == "2":
                while True:
                    try:
                        p_input = input(f"请输入分P号 (1-{len(pages)}): ").strip()
                        if 1 <= (p_num := int(p_input)) <= len(pages):
                            target_page = p_num
                            break
                        print(f"分P号必须在 1-{len(pages)} 范围内")
                    except ValueError:
                        print("请输入有效的数字")
    except:
        pass
    
    # 清晰度选择
    print('\n可选视频清晰度:')
    for qn, desc in BilibiliDownloader.QUALITY_MAP.items():
        print(f"{qn}: {desc}")
    
    try:
        quality = int(input('\n请输入清晰度代码 (默认80): ').strip() or 80)
        if quality not in BilibiliDownloader.QUALITY_MAP:
            quality = 80
            print("使用默认清晰度: 80")
    except ValueError:
        quality = 80
        print("使用默认清晰度: 80")
    
    # 开始下载
    print("\n开始下载...")
    downloader.download(video_input, quality, target_page)


if __name__ == '__main__':
    main()
