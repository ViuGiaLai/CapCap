import sys, os, subprocess

sample_video = "scratch/sample_movie.mp4"
output_recap = "scratch/sample_movie_recap.mp4"

filtergraph = "[0:v]trim=start=0.00:end=4.00,setpts=PTS-STARTPTS,hflip,scale=iw*1.10:ih*1.10,crop=w=iw/1.10:h=ih/1.10:x='(iw-ow)/2':y='(ih-oh)/2',scale=1280:720,setsar=1[vout0];[0:a]atrim=start=0.00:end=4.00,asetpts=PTS-STARTPTS[aout0];[0:v]trim=start=4.00:end=9.00,setpts=PTS-STARTPTS,scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)*t/5.00':y='(ih-oh)/2',scale=1280:720,setsar=1[vout1];[0:a]atrim=start=4.00:end=9.00,asetpts=PTS-STARTPTS[aout1];[0:v]trim=start=9.00:end=13.00,setpts=PTS-STARTPTS,setpts=PTS/1.15,tpad=stop_mode=clone:stop_duration=0.40,scale=1280:720,setsar=1[vout2];[0:a]atrim=start=9.00:end=13.00,asetpts=PTS-STARTPTS,atempo=1.15,apad=pad_dur=0.40[aout2];[vout0][aout0][vout1][aout1][vout2][aout2]concat=n=3:v=1:a=1[vfinal][afinal]"

cmd = ["ffmpeg", "-y", "-hide_banner", "-i", sample_video, "-filter_complex", filtergraph, "-map", "[vfinal]", "-map", "[afinal]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_recap]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("EXIT CODE:", res.returncode)
if res.returncode != 0:
    print("STDERR:\n", res.stderr[-2000:])
else:
    print("SUCCESSFULLY RENDERED!")
