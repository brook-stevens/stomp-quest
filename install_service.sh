set e
sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload 
sudo systemctl enable modep-display.service 
sudo systemctl start modep-display.service
sudo systemctl enable modep-control.service
sudo systemctl start modep-control.service 
