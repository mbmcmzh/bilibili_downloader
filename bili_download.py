import requests
import time
import urllib.request
import urllib.parse
import re
import os
import sys
from moviepy import VideoFileClip, AudioFileClip
import subprocess
import hashlib

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
        self.wbi_keys = None
        
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
        if bv_search := re.search(r'BV[a-zA-Z0-9]+', input_str):
            bvid = bv_search.group(0)
        else:
            raise Exception("输入的BV号格式不正确，或链接中不含BV号")
        
        base_url = 'https://api.bilibili.com/x/web-interface/view?'
        api_url = base_url + (f'bvid={bvid}')
        
        return bvid, api_url
    
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
    
    def _get_wbi_keys(self):
        """获取WBI签名密钥"""
        if self.wbi_keys:
            return self.wbi_keys
        
        try:
            resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=self._get_headers())
            resp.raise_for_status()
            json_content = resp.json()
            img_url = json_content['data']['wbi_img']['img_url']
            sub_url = json_content['data']['wbi_img']['sub_url']
            
            img_key = img_url.split('/')[-1].split('.')[0]
            sub_key = sub_url.split('/')[-1].split('.')[0]
            
            mixin_key_enc_tab = [
                46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
                33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
                61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
                36, 20, 34, 44, 52
            ]

            orig_key = img_key + sub_key
            mixin_key = ''.join([orig_key[i] for i in mixin_key_enc_tab])[:32]
            
            self.wbi_keys = {'mixin_key': mixin_key}
            return self.wbi_keys
        except Exception as e:
            raise Exception(f"获取WBI密钥失败: {e}")

    def _sign_wbi_params(self, params):
        """为WBI请求参数进行签名"""
        try:
            mixin_key = self._get_wbi_keys()['mixin_key']
            curr_time = round(time.time())
            params['wts'] = curr_time
            
            # 排序并移除特定字符
            params = dict(sorted(params.items()))
            query = urllib.parse.urlencode(params)
            query = re.sub(r"[!'()*]", "", query) # 移除在URL编码中保留的特殊字符

            w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
            params['w_rid'] = w_rid
            return params
        except Exception as e:
            raise Exception(f"WBI签名失败: {e}")
    
    def _get_dash_play_list(self, bvid, cid, quality):
        base_url = 'https://api.bilibili.com/x/player/wbi/playurl'
        params = {
            'cid': cid,
            'bvid': bvid,
            'qn': quality,
            'fourk': 1,
            'fnver': 0,
            'fnval': 4048
        }
        
        signed_params = self._sign_wbi_params(params)
        url_api = f"{base_url}?{urllib.parse.urlencode(signed_params)}"
        
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
                # WBI验证失败时，错误信息可能在message中，或者data中也有提示
                error_message = data.get('message', '')
                if 'data' in data and 'message' in data['data']:
                    error_message += f" ({data['data']['message']})"
                print(f"DASH API返回错误: {error_message}")
                return None
            
            play_data = data.get('data', {})
            
            if 'dash' in play_data:
                return self._parse_dash_data(play_data['dash'])
            return None
                
        except Exception as e:
            print(f"请求DASH API时发生异常: {e}")
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
    
    def _download_media(self, media_list, part_title, title, referer_url, page):
        """下载媒体文件（视频/音频）"""
        print(f'\n[正在下载P{page}段视频]: {part_title}')
        
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
            filename = f'{part_title}-{media_type}.m4s'
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
    
    def _merge_media_files(self, downloaded_files, title, part_title):
        """合并媒体文件"""
        video_path = os.path.join(self.download_dir, title)
        video_file = audio_file = None
        
        # 分离视频和音频文件
        for filepath, media_type in downloaded_files:
            if media_type == 'dash_video':
                video_file = filepath
            elif media_type == 'dash_audio':
                audio_file = filepath

        # 如果音视频文件都齐全，则合并
        if video_file and audio_file:
            output_path = os.path.join(video_path, f'{part_title}.mp4')
            print(f"\n正在合并音视频: {part_title}.mp4")
            self._merge_with_ffmpeg(video_file, audio_file, output_path)
            
            # 清理临时文件
            try:
                os.remove(video_file)
                os.remove(audio_file)
                print("临时文件清理完成")
            except OSError as e:
                print(f"清理临时文件失败: {e}")
        else:
            print("音视频文件不齐全，跳过合并步骤。")
    
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
            print("ffmpeg不可用，可能是未安装ffmpeg或未将ffmpeg添加到环境变量")
    
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
            bvid, api_url = self._parse_input(input_str)
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
                
                # 调试
                print(f'原始分P标题: {page_info["part"]}')
                print(f'处理后标题: {part_title}')
                
                # 构建referer URL
                referer_url = f"https://www.bilibili.com/video/BV{bvid}/?p={page}"
                
                # 获取下载链接
                media_list = self._get_dash_play_list(bvid, cid, quality)
                if not media_list:
                    print(f"获取下载链接失败，跳过P{page}")
                    continue
                
                # 下载并合并媒体文件
                downloaded_files = self._download_media(media_list, part_title, title, referer_url, page)
                self._merge_media_files(downloaded_files, title, part_title)
                print(f'[下载完成] P{page} - {part_title}')
                    
        except Exception as e:
            print(f"下载失败: {str(e)}")


def main():
    """主程序入口"""
    print('-' * 30 + 'B站视频下载助手' + '-' * 30)
    
    # 输入BV号或链接
    video_input = input('请输入您要下载的B站BV号或者视频链接地址: ')
    
    # 创建实例
    downloader = BilibiliDownloader()
    
    # 解析视频信息
    target_page = None
    try:
        bvid, api_url = downloader._parse_input(video_input)
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
            
            while True:
                choice = input("\n请选择:\n1. 下载全部分P\n2. 下载指定分P\n> ").strip()
                if choice == '1':
                    break
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
                    break
                print("无效的选择，请重新输入。")
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
