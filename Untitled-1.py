  135  cd ~/proyek/DeepStream-Yolo
  136  sudo chown -R $USER:$USER .
  137  export CUDA_VER=12.8
  138  make -C nvdsinfer_custom_impl_Yolo clean && make -C nvdsinfer_custom_impl_Yolo
  139  cd ~/proyek/DeepStream-Yolo