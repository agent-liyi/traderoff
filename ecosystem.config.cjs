// PM2 进程管理配置
// 使用方法：pm2 start ecosystem.config.cjs

module.exports = {
  apps: [
    {
      name: 'dongtaipingheng',
      script: 'node_modules/.bin/next',
      args: 'start',
      cwd: '/app/podcast-site',

      // 进程
      instances: 2,
      exec_mode: 'cluster',

      // 环境变量
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
      },

      // 自动重启
      max_memory_restart: '512M',
      restart_delay: 3000,

      // 日志
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '/var/log/podcast/err.log',
      out_file: '/var/log/podcast/out.log',
      merge_logs: true,

      // 优雅退出
      kill_timeout: 5000,
      listen_timeout: 10000,
    },
  ],
};
