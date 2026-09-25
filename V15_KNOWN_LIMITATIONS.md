# V5 KNOWN LIMITATIONS

1. **No real browser execution:** All Selenium operations are mocked with time.sleep()
2. **No Redis connection:** BullMQ Worker created but not connected to Redis
3. **No R2/DB services:** All R2, DB, and credits operations are stubs
4. **No CDP events:** No Browser.downloadWillBegin or downloadProgress handlers
5. **No real downloads:** File download pipeline is mocked
6. **No real Gemini API:** Image generation is mocked
7. **No real WMR service:** Watermark removal is mocked
8. **No full end-to-end test:** Requires Chrome, Gemini, WMR, R2, DB, Redis
9. **Linux/Colab only:** Virtual display setup assumes Linux environment
10. **Single-machine only:** No distributed deployment support

## Known Defects

### V15 Skeleton
- process_gemini() and process_wmr() use time.sleep() instead of real browser
- BullMQ Worker not attached to Redis
- R2/DB/credits are empty stubs
- No CDP event listeners
- No real download handling
- No PIL validation
- No WebP conversion

### Historical Defects (Fixed in V14 N2N, not yet in V15)
- Edge contamination in some versions
- Filename-based download matching
- asyncio.run() in Colab
- Import before bootstrap
- Duplicate function definitions
- Hardcoded credential paths
- Tuple-vs-Path issues
- MOJIBAKE in source files
- Production `except: pass` blocks
- Incomplete WMR worker loops
