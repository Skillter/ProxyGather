sudo apt-get update -y
sudo apt-get install -y python3-tk python3-dev xvfb libgl1-mesa-glx libglib2.0-0

# install chrome
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y
rm google-chrome-stable_current_amd64.deb
cd -

