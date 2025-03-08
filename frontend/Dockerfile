# Build stage
FROM node:20-slim AS builder

# Set working directory
WORKDIR /app

# Install dependencies
COPY package*.json ./
COPY bun.lockb ./

# Use build-time caching
RUN --mount=type=cache,target=/app/.npm \
  npm ci --cache /app/.npm

# Copy source code
COPY . .

# Set environment to production
ENV NODE_ENV=production \
  NEXT_TELEMETRY_DISABLED=1

# Build application
RUN npm run build

# Production stage
FROM node:20-slim AS runner

# Set working directory
WORKDIR /app

# Set environment variables
ENV NODE_ENV=production \
  NEXT_TELEMETRY_DISABLED=1

# Add non-root user
RUN addgroup --system --gid 1001 nodejs && \
  adduser --system --uid 1001 nextjs

# Set directory permissions
RUN mkdir -p /app/.next && \
  chown -R nextjs:nodejs /app

# Copy necessary files from builder
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/next.config.ts ./
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD node -e "require('http').request({port: 3000, path: '/api/health'}, (r) => process.exit(r.statusCode === 200 ? 0 : 1)).end()" || exit 1

# Start application
CMD ["node", "server.js"] 