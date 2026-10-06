Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"

  # Add all cluster hosts
  $update_hosts = <<-SHELL
    sudo tee -a /etc/hosts > /dev/null <<'EOF'
192.168.56.10 controller
192.168.56.11 worker1
192.168.56.12 worker2
192.168.56.13 worker3
EOF
  SHELL

  # Execution on all VMs
  config.vm.provision "shell", inline: $update_hosts

  config.vm.define "controller" do |controller|
    controller.vm.hostname = "controller"
    controller.vm.network "private_network", ip: "192.168.56.10"
    controller.vm.provider "virtualbox" do |vb|
      vb.memory = "2048"
      vb.cpus = 2
    end
  end

  (1..3).each do |i|
    config.vm.define "worker#{i}" do |worker|
      worker.vm.hostname = "worker#{i}"
      worker.vm.network "private_network", ip: "192.168.56.#{10+i}"
      worker.vm.provider "virtualbox" do |vb|
        vb.memory = "1024"
        vb.cpus = 1
      end
    end
  end
end
